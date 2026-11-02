# rust2pyton

## How to execute

```shell
uv venv
source .venv/bin/activate
uv add maturin
cargo build --release
# maturin build --release
python demo.py --use-maturin
python demo.py --no-use-maturin
```
