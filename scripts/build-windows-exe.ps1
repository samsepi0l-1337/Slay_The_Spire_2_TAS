Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

uv sync --locked --extra build --extra dev
if ($LASTEXITCODE -ne 0) { throw "dependency sync failed: $LASTEXITCODE" }
$env:PYTHONPATH = "src"
uv run --locked pyinstaller --onefile --name sts2-tas src/sts2_tas/cli.py
if ($LASTEXITCODE -ne 0) { throw "executable build failed: $LASTEXITCODE" }
