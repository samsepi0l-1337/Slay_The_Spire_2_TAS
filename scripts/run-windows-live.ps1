Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$GameDir = "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2"
$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $RepoDir "src\sts2_tas"))) {
    $RepoDir = (Get-Location).Path
}

Set-Location $RepoDir
$env:PYTHONPATH = "src"
$env:STS2_GAME_DIR = $GameDir

Write-Output "Building Harmony telemetry mod and fixture bridge"
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release
if ($LASTEXITCODE -ne 0) { throw "mod build failed" }
dotnet build "bridge\Sts2TelemetryBridge\Sts2TelemetryBridge.csproj" -c Release
if ($LASTEXITCODE -ne 0) { throw "bridge build failed" }

Write-Output "Starting fixture pipe-serve on 127.0.0.1:28771"
$serve = Start-Process -FilePath "dotnet" -ArgumentList @(
    "run", "--project", "bridge\Sts2TelemetryBridge\Sts2TelemetryBridge.csproj", "-c", "Release", "--no-build",
    "--", "pipe-serve", "--fixture", "data\fixtures\telemetry-combat.json", "--listen", "127.0.0.1:28771"
) -PassThru -NoNewWindow
Start-Sleep -Seconds 3

try {
    New-Item -ItemType Directory -Force -Path "models" | Out-Null
    Write-Output "Running Q* live loop"
    uv run --extra dev sts2-tas run-live `
        --transport tcp:127.0.0.1:28771 `
        --model models\qstar-live.json `
        --output models\qstar-live.jsonl `
        --search-depth 1 `
        --max-steps 8 `
        --execute
}
finally {
    if (-not $serve.HasExited) {
        Stop-Process -Id $serve.Id -Force
    }
}
