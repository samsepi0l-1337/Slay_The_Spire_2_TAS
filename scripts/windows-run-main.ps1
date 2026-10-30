Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

if (-not (Test-Path ".git")) { throw "expected an existing repository" }
$dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "git status failed: $LASTEXITCODE" }
if ($dirty) { throw "working tree has local changes; update it manually" }
$branch = git branch --show-current
if ($LASTEXITCODE -ne 0) { throw "branch check failed: $LASTEXITCODE" }
if ($branch -ne "main") { throw "expected main branch; refusing to switch branches" }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw "fast-forward update failed: $LASTEXITCODE" }

Write-Output "=== git ==="
git log -1 --oneline
if ($LASTEXITCODE -ne 0) { throw "git command failed: $LASTEXITCODE" }

Write-Output "=== uv run pytest ==="
uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100 -q
if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }

Write-Output "=== build bridge ==="
dotnet build "bridge\Sts2TelemetryBridge\Sts2TelemetryBridge.csproj" -c Release
if ($LASTEXITCODE -ne 0) { throw "dotnet command failed: $LASTEXITCODE" }
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release -p:DeployMod=true
if ($LASTEXITCODE -ne 0) { throw "dotnet command failed: $LASTEXITCODE" }

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
    uv run --locked --extra dev python -m sts2_tas.cli run-live `
        --transport $transport `
        --model models\qstar-live.json `
        --output models\qstar-live.jsonl `
        --search-depth 1 `
        --max-steps 8 `
        --execute
    if ($LASTEXITCODE -ne 0) { throw "uv command failed: $LASTEXITCODE" }
} finally {
    if ($serve -and -not $serve.HasExited) { Stop-Process -Id $serve.Id -Force }
}
