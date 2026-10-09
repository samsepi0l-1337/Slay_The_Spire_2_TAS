Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
Set-Location "C:\Users\steep\sts2-tas-qstar"
$env:PYTHONPATH = "src"

Write-Output "=== uv version ==="
uv --version
if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }

Write-Output "=== uv run sts2-tas --help ==="
uv run --locked --extra dev python -m sts2_tas.cli --help
if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }

Write-Output "=== uv run pytest ==="
uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100 -q
if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }

$exe = Join-Path $PWD "bridge\Sts2TelemetryBridge\bin\Release\net8.0\Sts2TelemetryBridge.exe"
$fixture = Join-Path $PWD "data\fixtures\telemetry-combat.json"
if (-not (Test-Path $exe)) {
    Write-Output "=== building fixture bridge ==="
    dotnet build "bridge\Sts2TelemetryBridge\Sts2TelemetryBridge.csproj" -c Release
    if ($LASTEXITCODE -ne 0) { throw "dotnet command failed: $LASTEXITCODE" }
}
New-Item -ItemType Directory -Force -Path "models" | Out-Null

Write-Output "=== uv run run-live ==="
$serve = Start-Process -FilePath $exe -ArgumentList @(
    "pipe-serve", "--fixture", $fixture, "--listen", "127.0.0.1:28771"
) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
try {
    uv run --locked --extra dev python -m sts2_tas.cli run-live `
        --transport tcp:127.0.0.1:28771 `
        --model models\qstar-live.json `
        --output models\qstar-live.jsonl `
        --search-depth 1 `
        --max-steps 8 `
        --execute
    if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }
    Write-Output "=== model ==="
    Test-Path "models\qstar-live.json"
} finally {
    if (-not $serve.HasExited) { Stop-Process -Id $serve.Id -Force }
}
