$ErrorActionPreference = "Stop"

uv sync --extra build
uv run --extra build pyinstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name sts2-tas `
    --collect-all torch `
    src/sts2_tas/__main__.py

$exe = "dist/sts2-tas.exe"
if (-not (Test-Path $exe)) {
    throw "Expected executable was not created: $exe"
}

Write-Output $exe
