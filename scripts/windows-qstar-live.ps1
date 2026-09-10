Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;" + $env:PATH
Set-Location "C:\Users\steep\sts2-tas-qstar"
$env:PYTHONPATH = "src"

$exe = Join-Path $PWD "bridge\Sts2TelemetryBridge\bin\Release\net8.0\Sts2TelemetryBridge.exe"
$fixture = Join-Path $PWD "data\fixtures\telemetry-combat.json"
New-Item -ItemType Directory -Force -Path "models" | Out-Null

$serve = Start-Process -FilePath $exe -ArgumentList @(
    "pipe-serve", "--fixture", $fixture, "--listen", "127.0.0.1:28771"
) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
try {
    uv run --extra dev python -m sts2_tas.cli run-live `
        --transport tcp:127.0.0.1:28771 `
        --model models\qstar-live.json `
        --output models\qstar-live.jsonl `
        --search-depth 1 `
        --max-steps 8 `
        --execute
    Write-Output "---model exists---"
    Test-Path "models\qstar-live.json"
    Write-Output "---jsonl---"
    if (Test-Path "models\qstar-live.jsonl") { Get-Content "models\qstar-live.jsonl" }
} finally {
    if (-not $serve.HasExited) { Stop-Process -Id $serve.Id -Force }
}
