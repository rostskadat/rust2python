use chrono::{Duration, Local, NaiveDate, NaiveDateTime};
use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use std::collections::HashMap;
use std::path::PathBuf;

#[pyfunction(name = "fast_sort")]
pub fn py_fast_sort(mut integers: Vec<i64>) -> Vec<i64> {
    integers.sort_unstable();
    integers
}

#[pyfunction(name = "into_pyobject")]
fn py_into_pyobject(py: Python<'_>) -> PyResult<Py<PyDict>> {
    let mut data: HashMap<String, Vec<(String, String, f64)>> = HashMap::new();
    data.entry("1".to_string())
        .or_default()
        .push(("2026/10/17".to_string(), "1".to_string(), 0.0));
    data.entry("2".to_string())
        .or_default()
        .push(("2026/10/17".to_string(), "2".to_string(), 0.5));
    data.entry("3".to_string())
        .or_default()
        .push(("2026/10/17".to_string(), "3".to_string(), 1.0));
    let mut python_data: HashMap<String, Vec<Py<PyTuple>>> = HashMap::new();
    for (key, values) in data {
        let mut python_values = Vec::with_capacity(values.len());
        for (date, hour, energy_kwh) in values {
            let value = PyList::empty(py);
            value.append(date)?;
            value.append(hour)?;
            value.append(energy_kwh)?;
            python_values.push(value.to_tuple().unbind());
        }
        python_data.insert(key, python_values);
    }
    Ok(python_data.into_pyobject(py)?.unbind())
}

#[pyfunction(name = "extract_loads")]
pub fn py_extract_loads(
    py: Python<'_>,
    load_max_age_in_days: i64,
    files: Vec<PathBuf>,
) -> PyResult<Py<PyDict>> {
    let age = Duration::try_days(load_max_age_in_days)
        .ok_or_else(|| PyValueError::new_err("load_max_age_in_days is out of range"))?;
    let cutoff_datetime = Local::now()
        .naive_local()
        .checked_sub_signed(age)
        .ok_or_else(|| PyValueError::new_err("load_max_age_in_days is out of range"))?;
    let locale_atof = py.import("locale")?.getattr("atof")?;
    let mut loads: HashMap<String, Vec<(String, String, f64)>> = HashMap::new();

    for file in files {
        let mut reader = csv::ReaderBuilder::new()
            .delimiter(b';')
            .from_path(&file)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
        let headers = reader
            .headers()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))?
            .clone();
        if headers.is_empty() {
            continue;
        }
        let column_index = |name: &str| {
            headers
                .iter()
                .position(|header| header == name)
                .ok_or_else(|| PyKeyError::new_err(name.to_owned()))
        };
        let cups_index = column_index("CUPS")?;
        let date_index = column_index("Fecha")?;
        let hour_index = column_index("Hora")?;
        let energy_index = column_index("AE_kWh")?;

        for record in reader.records() {
            let row = record.map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
            let field = |index| {
                row.get(index)
                    .ok_or_else(|| PyValueError::new_err("CSV row is missing a required field"))
            };
            let cups = field(cups_index)?.trim().to_owned();
            let date = field(date_index)?.trim().to_owned();
            let parsed_date = NaiveDate::parse_from_str(&date, "%d/%m/%Y")
                .map_err(|error| PyValueError::new_err(error.to_string()))?;
            let parsed_datetime = NaiveDateTime::new(parsed_date, chrono::NaiveTime::MIN);
            if parsed_datetime < cutoff_datetime {
                continue;
            }

            let hour = field(hour_index)?.trim().to_owned();
            let energy = field(energy_index)?.trim();
            let energy_kwh = if energy.is_empty() {
                0.0
            } else {
                let parsed_energy = if energy.contains(',') {
                    energy
                        .replace(',', ".")
                        .parse::<f64>()
                        .map_err(|error| PyValueError::new_err(error.to_string()))
                } else {
                    locale_atof
                        .call1((energy,))
                        .and_then(|value| value.extract::<f64>())
                };
                match parsed_energy {
                    Ok(value) => value,
                    Err(error) if error.is_instance_of::<PyValueError>(py) => {
                        println!(
                            "Could not parse AE_kWh '{}' in file '{}'",
                            energy,
                            file.display()
                        );
                        continue;
                    }
                    Err(error) => return Err(error),
                }
            };

            loads
                .entry(cups)
                .or_default()
                .push((date, hour, energy_kwh));
        }
    }

    let mut python_loads: HashMap<String, Vec<Py<PyTuple>>> = HashMap::with_capacity(loads.len());
    for (cups, load_rows) in loads {
        let mut rows = Vec::with_capacity(load_rows.len());
        for (date, hour, energy_kwh) in load_rows {
            let row = PyList::empty(py);
            row.append(date)?;
            row.append(hour)?;
            row.append(energy_kwh)?;
            rows.push(row.to_tuple().unbind());
        }
        python_loads.insert(cups, rows);
    }

    Ok(python_loads.into_pyobject(py)?.unbind())
}

#[pymodule]
fn rust2python(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(py_fast_sort, module)?)?;
    module.add_function(wrap_pyfunction!(py_extract_loads, module)?)?;
    module.add_function(wrap_pyfunction!(py_into_pyobject, module)?)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fast_sort() {
        assert_eq!(py_fast_sort(vec![3, -1, 2, -1, 0]), vec![-1, -1, 0, 2, 3]);
        assert_eq!(py_fast_sort(vec![]), Vec::<i64>::new());
        assert_eq!(py_fast_sort(vec![42]), vec![42]);
        assert_eq!(py_fast_sort(vec![1, 2, 3]), vec![1, 2, 3]);
        assert_eq!(py_fast_sort(vec![3, 2, 1]), vec![1, 2, 3]);
        assert_eq!(
            py_fast_sort(vec![i64::MAX, i64::MIN]),
            vec![i64::MIN, i64::MAX]
        );
    }
}
