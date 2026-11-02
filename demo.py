"""Run `cargo build --release`, then `python3 demo.py` to compare sorting and load extraction.

USE Maturin to package rust code as a Python module.
"""

import argparse
import csv
import importlib.util
import locale
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from statistics import median
from time import perf_counter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def python_merge_sort(integers: list[int]) -> list[int]:
    if len(integers) < 2:
        return integers.copy()

    midpoint = len(integers) // 2
    left = python_merge_sort(integers[:midpoint])
    right = python_merge_sort(integers[midpoint:])
    merged = []
    left_index = 0
    right_index = 0

    while left_index < len(left) and right_index < len(right):
        if left[left_index] <= right[right_index]:
            merged.append(left[left_index])
            left_index += 1
        else:
            merged.append(right[right_index])
            right_index += 1

    merged.extend(left[left_index:])
    merged.extend(right[right_index:])
    return merged


def extract_loads(load_max_age_in_days: int, files: list):
    today = datetime.today()
    cutoff_date = today - timedelta(days=load_max_age_in_days)
    loads = {}
    for file in files:
        with open(file, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                cups = row["CUPS"].strip()
                fecha = row["Fecha"].strip()
                fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")

                if fecha_dt < cutoff_date:
                    continue

                hora = row["Hora"].strip()
                ae_kwh = row["AE_kWh"].strip()

                # Convert AE_kWh to float
                try:
                    if ae_kwh != "":
                        ae_kwh_val = (
                            float(ae_kwh.replace(",", "."))
                            if "," in ae_kwh
                            else locale.atof(ae_kwh)
                        )
                    else:
                        ae_kwh_val = 0.0
                except ValueError as e:
                    logger.error(
                        f"Could not parse AE_kWh '{ae_kwh}' in file '{file}'")
                    continue

                if cups not in loads:
                    loads[cups] = []
                loads[cups].append((fecha, hora, ae_kwh_val))
    return loads


def benchmark_sort(
    sort_function: Callable[[list[int]], list[int]],
    integers: list[int],
    expected: list[int],
    repetitions: int,
) -> float:
    durations = []
    for _ in range(repetitions):
        start = perf_counter()
        result = sort_function(integers)
        durations.append(perf_counter() - start)
        if result != expected:
            raise RuntimeError("Sorting produced an incorrect result.")
    return median(durations)


def benchmark_loads(
    load_function: Callable[
        [int, list[Path]], dict[str, list[tuple[str, str, float]]]
    ],
    load_max_age_in_days: int,
    files: list[Path],
    expected: dict[str, list[tuple[str, str, float]]],
    repetitions: int,
) -> float:
    durations = []
    for _ in range(repetitions):
        start = perf_counter()
        result = load_function(load_max_age_in_days, files)
        durations.append(perf_counter() - start)
        if result != expected:
            raise RuntimeError("Load extraction produced an incorrect result.")
    return median(durations)


def load_rust_module(use_maturin: bool = False):
    if use_maturin:
        import rust2python
        return rust2python, "default"
    else:
        target = Path(__file__).resolve().parent / "target"
        profile = "release" if (target / "release/librust2python.so").is_file() else "debug"
        library_path = target / profile / "librust2python.so"
        if not library_path.is_file():
            raise SystemExit("Library not found. Run `cargo build --release` first.")

        spec = importlib.util.spec_from_file_location("rust2python", library_path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"Cannot load the Rust library: {library_path}")

        rust2python = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rust2python)
        return rust2python, profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--use-maturin",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Load the Rust module installed by maturin (default). "
            "Use --no-use-maturin to load it from target/ instead."
        ),
    )
    args = parser.parse_args()

    print("Loading Rust module...")
    rust2python, profile = load_rust_module(use_maturin=args.use_maturin)

    count = 100_000
    repetitions = 1
    random = Random(42)
    integers = [random.randint(-1_000_000, 1_000_000) for _ in range(count)]
    original = integers.copy()
    expected = sorted(integers)

    print("Benchmarking sort methods...")
    python_seconds = benchmark_sort(python_merge_sort, integers, expected, repetitions)
    rust_seconds = benchmark_sort(rust2python.fast_sort, integers, expected, repetitions)
    if integers != original:
        raise RuntimeError("Sorting modified the original input.")

    load_max_age_in_days = 730
    assets = Path(__file__).resolve().parent / "assets"
    load_files = sorted(assets.glob("*.csv"))
    expected_loads = extract_loads(load_max_age_in_days, load_files)
    print("Benchmarking load extraction methods...")
    python_load_seconds = benchmark_loads(
        extract_loads,
        load_max_age_in_days,
        load_files,
        expected_loads,
        repetitions,
    )
    rust_load_seconds = benchmark_loads(
        rust2python.extract_loads,
        load_max_age_in_days,
        load_files,
        expected_loads,
        repetitions,
    )

    print("Rust timing includes Python/Rust conversion overhead.")
    print(" ")
    print(f"Integers: {count:,}; runs: {repetitions}; Rust profile: {profile}")
    print(f"Pure Python merge sort (median): {python_seconds:.6f} s")
    print(f"Rust fast_sort (median):         {rust_seconds:.6f} s")
    print(f"Python time / Rust time:         {python_seconds / rust_seconds:.2f}x")
    print("Both results match sorted(); the original input is unchanged.")
    print(" ")
    print(f"Load files: {len(load_files)}; age limit: {load_max_age_in_days} days")
    print(f"Python extract_loads (median):   {python_load_seconds:.6f} s")
    print(f"Rust extract_loads (median):     {rust_load_seconds:.6f} s")
    print(f"Python time / Rust time:         {python_load_seconds / rust_load_seconds:.2f}x")
    print(" ")
    print("Both load extraction results match.")
    if profile == "debug":
        print("Run `cargo build --release` for an optimized Rust benchmark.")
        
    print(" ")
    print("Calling into_pyobject.")
    print(rust2python.into_pyobject())


if __name__ == "__main__":
    main()