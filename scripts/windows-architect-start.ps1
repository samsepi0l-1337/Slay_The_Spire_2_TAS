Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

Write-Output "=== stop previous TAS and STS2 ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'run-live' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
cmd /c "taskkill /F /IM SlayTheSpire2.exe >nul 2>&1"
Start-Sleep -Seconds 5
if (Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue) {
    throw "SlayTheSpire2.exe still running after taskkill"
}

Write-Output "=== build and deploy Harmony mod ==="
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release
if ($LASTEXITCODE -ne 0) { throw "mod build failed" }
$gameMods = "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\mods\Sts2TasMod"
New-Item -ItemType Directory -Force -Path $gameMods | Out-Null
Copy-Item "bridge\Sts2TasMod\bin\Release\net9.0\Sts2TasMod.dll" $gameMods -Force
Copy-Item "bridge\Sts2TasMod\Sts2TasMod.json" $gameMods -Force

Get-Process -Name "SlayTheSpire2" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
$task = "STS2TasLaunch"
$tr = "cmd.exe /c start steam://rungameid/2868840"
Write-Output "=== launch STS2 via Steam on interactive console ==="
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

Write-Output "=== wait for named pipe sts2-tas ==="
$pipeDeadline = (Get-Date).AddMinutes(3)
$opened = $false
while ((Get-Date) -lt $pipeDeadline) {
    try {
        $client = New-Object System.IO.Pipes.NamedPipeClientStream(".", "sts2-tas", [System.IO.Pipes.PipeDirection]::InOut)
        $client.Connect(1000)
        $client.Dispose()
        $opened = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $opened) { throw "named pipe sts2-tas did not appear; enable mods in the game window" }
Write-Output "pipe attached"

New-Item -ItemType Directory -Force -Path "models" | Out-Null
$log = Join-Path $Repo "models\architect-live.log"
$runner = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Repo "scripts\windows-architect-runlive.ps1")
) -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") -PassThru -WindowStyle Hidden
Write-Output ("live pid=" + $runner.Id)
Write-Output ("log=" + $log)
