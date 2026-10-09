Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

Write-Output "=== pull main ==="
if (-not (Test-Path ".git")) { throw "expected an existing repository" }
$dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "git status failed: $LASTEXITCODE" }
if ($dirty) { throw "working tree has local changes; update it manually" }
$branch = git branch --show-current
if ($LASTEXITCODE -ne 0) { throw "branch check failed: $LASTEXITCODE" }
if ($branch -ne "main") { throw "expected main branch; refusing to switch branches" }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw "fast-forward update failed: $LASTEXITCODE" }
git log -1 --oneline
if ($LASTEXITCODE -ne 0) { throw "git command failed: $LASTEXITCODE" }

Write-Output "=== stop previous TAS and STS2 ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'run-live' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
cmd /c "taskkill /F /IM SlayTheSpire2.exe >nul 2>&1"
Start-Sleep -Seconds 5

Write-Output "=== build and deploy Harmony mod ==="
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release -p:DeployMod=true
if ($LASTEXITCODE -ne 0) { throw "mod build failed" }
# Deployment preserves existing trust; configure any required signing outside this script.

$taskGame = "STS2TasLaunch"
$trGame = "cmd.exe /c start steam://rungameid/2868840"
schtasks /Create /TN $taskGame /TR $trGame /SC ONCE /ST 23:59 /F /IT | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks command failed: $LASTEXITCODE" }
schtasks /Run /TN $taskGame | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks command failed: $LASTEXITCODE" }

$deadline = (Get-Date).AddMinutes(2)
$proc = $null
while ((Get-Date) -lt $deadline) {
    $proc = Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue
    if ($proc) { break }
    Start-Sleep -Seconds 2
}
if (-not $proc) { throw "SlayTheSpire2.exe did not start" }
Write-Output ("STS2 pid=" + $proc.Id)

$pipeDeadline = (Get-Date).AddMinutes(3)
$opened = $false
while ((Get-Date) -lt $pipeDeadline) {
    $pipes = [IO.Directory]::GetFiles("\\.\pipe\") | Where-Object { $_ -like "*sts2-tas" }
    if ($pipes) {
        $opened = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $opened) { throw "named pipe sts2-tas did not appear" }
Write-Output "pipe listening"

New-Item -ItemType Directory -Force -Path "models" | Out-Null
$runlive = Join-Path $Repo "scripts\windows-architect-runlive.ps1"
$taskTas = "STS2TasPlay"
$trTas = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runlive`""
Write-Output "=== start TAS in console session ==="
schtasks /Create /TN $taskTas /TR $trTas /SC ONCE /ST 23:59 /F /IT | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks command failed: $LASTEXITCODE" }
schtasks /Run /TN $taskTas | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks command failed: $LASTEXITCODE" }
$log = Join-Path $Repo "models\play-one-run.log"
$err = Join-Path $Repo "models\play-one-run.err"
$tasDeadline = (Get-Date).AddSeconds(20)
$tasUp = $false
while ((Get-Date) -lt $tasDeadline) {
    $live = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'run-live' }
    if ($live) { $tasUp = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $tasUp) {
    $direct = Start-Process -FilePath "powershell.exe" -WorkingDirectory $Repo -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $runlive
    ) -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -WindowStyle Hidden
    Write-Output ("TAS direct pid=" + $direct.Id)
} else {
    Write-Output "TAS already running from schtasks"
}
Write-Output "status=models\one-run.status.json"
