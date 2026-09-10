Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

if (-not (Test-Path (Join-Path $Repo ".git"))) {
    git init
    git remote add origin https://github.com/samsepi0l-1337/Slay_The_Spire_2_TAS.git
}
git fetch origin main
git checkout -f -B main origin/main

Write-Output "=== git ==="
git log -1 --oneline

Write-Output "=== uv run pytest ==="
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100 -q

Write-Output "=== build bridge ==="
dotnet build "bridge\Sts2TelemetryBridge\Sts2TelemetryBridge.csproj" -c Release
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release

$game = Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue
if (-not $game) {
    Write-Output "=== launching STS2 ==="
    Start-Process "steam://rungameid/2868840"
    Start-Sleep -Seconds 8
    $game = Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue
}
if ($game) {
    Write-Output ("STS2 pid=" + $game.Id)
} else {
    Write-Output "STS2 not running; fixture pipe-serve"
}

$exe = Join-Path $Repo "bridge\Sts2TelemetryBridge\bin\Release\net8.0\Sts2TelemetryBridge.exe"
$fixture = Join-Path $Repo "data\fixtures\telemetry-combat.json"
New-Item -ItemType Directory -Force -Path "models" | Out-Null

$transport = "pipe:sts2-tas"
$serve = $null
if (-not $game) {
    $transport = "tcp:127.0.0.1:28771"
    $serve = Start-Process -FilePath $exe -ArgumentList @(
        "pipe-serve", "--fixture", $fixture, "--listen", "127.0.0.1:28771"
    ) -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Write-Output "=== uv run run-live $transport ==="
try {
    uv run --extra dev python -m sts2_tas.cli run-live `
        --transport $transport `
        --model models\qstar-live.json `
        --output models\qstar-live.jsonl `
        --search-depth 1 `
        --max-steps 8 `
        --execute
} finally {
    if ($serve -and -not $serve.HasExited) { Stop-Process -Id $serve.Id -Force }
}
