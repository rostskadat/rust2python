# 🦀 rust2python

A small demo of calling Rust from Python with [PyO3](https://pyo3.rs/), comparing
pure-Python implementations against their Rust counterparts for both speed and
correctness.

The project exposes a Rust extension module (`rust2python`) with two benchmarked
functions, plus a helper that shows how Rust values are converted into Python
objects:

| Function | Description |
| --- | --- |
| `fast_sort(integers)` | Sorts a list of integers using Rust's `sort_unstable`. |
| `extract_loads(load_max_age_in_days, files)` | Parses a set of `;`-separated CSV files, filters rows by date, and groups energy readings (`AE_kWh`) by `CUPS`. |
| `into_pyobject()` | Builds a small nested `dict`/`tuple` structure to demonstrate PyO3 conversions. |

`demo.py` runs each operation in Python and Rust, verifies that both produce the
same result, and reports the median runtime. It can load the Rust code either
from a maturin-installed package or directly from the compiled `cdylib` in
`target/`, which makes it easy to compare the two loading strategies.

## ✅ Prerequisites

- Rust toolchain (edition 2024, so a recent `cargo` is required)
- Python 3.9+
- [`uv`](https://docs.astral.sh/uv/) (used below, but plain `pip`/`venv` works too)
- `maturin` for the packaged build

## 🚀 How to execute

```shell
uv venv
source .venv/bin/activate
uv add maturin

# Option A: build a wheel and install it into the virtualenv
maturin develop
python demo.py --use-maturin

# Option B: build with cargo and load the shared library directly
cargo build --release
python demo.py --no-use-maturin
```

## ⚙️ Command-line options

| Option | Default | Description |
| --- | --- | --- |
| `--use-maturin` | enabled | Import the module installed by `maturin develop`. |
| `--no-use-maturin` | – | Load `target/release/librust2python.so` (or `target/debug/...`) directly with `importlib`. |

`--no-use-maturin` falls back to the `debug` build when no release library is
present, and exits with an error if neither exists.

## 📊 Sample output

Results from a release build (`--no-use-maturin`); timings vary by machine.

```text
Loading Rust module...
Benchmarking sort methods...
Benchmarking load extraction methods...
Rust timing includes Python/Rust conversion overhead.

Integers: 100,000; runs: 1; Rust profile: release
Pure Python merge sort (median): 0.297070 s
Rust fast_sort (median):         0.007335 s
Python time / Rust time:         40.50x
Both results match sorted(); the original input is unchanged.

Load files: 5; age limit: 730 days
Python extract_loads (median):   0.367493 s
Rust extract_loads (median):     0.072003 s
Python time / Rust time:         5.10x

Both load extraction results match.

Calling into_pyobject.
{'2': [('2026/10/17', '2', 0.5)], '3': [('2026/10/17', '3', 1.0)], '1': [('2026/10/17', '1', 0.0)]}
```

The same run against a maturin install reports `Rust profile: default` and
slower Rust timings, because `maturin develop` produces a debug build by
default. Use `maturin develop --release` to compare optimized builds.

## 🗂️ Project structure

```text
.
├── src/lib.rs      # PyO3 module: fast_sort, extract_loads, into_pyobject
├── demo.py         # Python/Rust benchmark harness and CLI
├── assets/         # Sample CSV files used by extract_loads
├── Cargo.toml      # Rust crate configuration
└── pyproject.toml  # maturin build configuration
```

## 🧪 Tests

```shell
cargo test
```
