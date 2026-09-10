Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

Write-Output "=== build and deploy Harmony mod ==="
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release
$gameMods = "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\mods\Sts2TasMod"
New-Item -ItemType Directory -Force -Path $gameMods | Out-Null
Copy-Item "bridge\Sts2TasMod\bin\Release\net9.0\Sts2TasMod.dll" $gameMods -Force
Copy-Item "bridge\Sts2TasMod\Sts2TasMod.json" $gameMods -Force

$exe = "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.exe"
$task = "STS2TasLaunch"
$tr = "'" + $exe + "'"
Write-Output "=== launch STS2 on interactive console ==="
schtasks /Create /TN $task /TR $tr /SC ONCE /ST 23:59 /F /IT | Out-Null
schtasks /Run /TN $task | Out-Null

$deadline = (Get-Date).AddMinutes(2)
$proc = $null
while ((Get-Date) -lt $deadline) {
    $proc = Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue
    if ($proc) { break }
    Start-Sleep -Seconds 2
}
if (-not $proc) { throw "SlayTheSpire2.exe did not start" }
Write-Output ("STS2 pid=" + $proc.Id)

Write-Output "=== wait for \\\\.\\pipe\\sts2-tas ==="
$pipeDeadline = (Get-Date).AddMinutes(2)
$opened = $false
while ((Get-Date) -lt $pipeDeadline) {
    try {
        $handle = [System.IO.File]::Open("\\.\pipe\sts2-tas", [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite)
        $handle.Close()
        $opened = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $opened) { throw "named pipe sts2-tas did not appear; enable mods in STS2 and retry" }
Write-Output "pipe attached"

New-Item -ItemType Directory -Force -Path "models" | Out-Null
Write-Output "=== uv run-live until Architect ==="
uv run --extra dev python -m sts2_tas.cli run-live `
    --transport pipe:sts2-tas `
    --model models\qstar-live.json `
    --output models\qstar-live.jsonl `
    --search-depth 1 `
    --max-steps 100000 `
    --until-clear `
    --execute
