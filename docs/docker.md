# Docker

Docker is for Python 3.14 CLI/model/fixture work. It is not the desktop automation boundary for Slay the Spire 2.

## Build

```bash
docker build -t sts2-tas:local .
docker run --rm sts2-tas:local --help
```

## Windows PowerShell

Docker Desktop should use Linux containers mode. Mount the repository as a volume so datasets, fixtures, and models stay outside the image.

```powershell
docker build -t sts2-tas:local .
docker run --rm -v "${PWD}:/workspace" sts2-tas:local --help
```

## Python Runtime

The repository uses Python 3.14. `.python-version` is pinned to `3.14.5` so local and Windows helper environments resolve the same interpreter family.

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

If editable import resolution fails in a local checkout, run verification with `PYTHONPATH=src` while fixing the environment:

```bash
PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

## Runtime Boundary

The container may run schema tests, fixture-based `bridge-smoke`, `env-step`, training, and evaluation. It does not capture the Windows desktop, attach to the game, or send native input to the game window.

Live automation requires a local interactive Windows session with the game visible, the C# telemetry bridge loaded, and explicit `--execute` when native input is intended. Docker can process files produced by that host session but should not be treated as the input/capture executor.

## Generated Data

Keep generated artifacts outside the image:

- `data/*.jsonl`
- `data/*.db`
- `data/*.parquet`
- `data/*.png`
- `models/*`
- `mlruns/`
