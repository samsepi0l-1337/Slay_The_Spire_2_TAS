Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

uv sync --extra build --extra dev
$env:PYTHONPATH = "src"
uv run pyinstaller --onefile --name sts2-tas src/sts2_tas/cli.py
