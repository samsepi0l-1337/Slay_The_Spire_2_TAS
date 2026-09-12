Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
$Repo = "C:\Users\steep\sts2-tas-qstar"
Set-Location $Repo
$env:PYTHONPATH = "src"

Write-Output "=== pull main ==="
if (Test-Path ".git") {
    git fetch origin main
    git checkout -f -B main origin/main
}
git log -1 --oneline

Write-Output "=== stop previous TAS and STS2 ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'run-live' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
cmd /c "taskkill /F /IM SlayTheSpire2.exe >nul 2>&1"
Start-Sleep -Seconds 5

Write-Output "=== build and deploy Harmony mod ==="
dotnet build "bridge\Sts2TasMod\Sts2TasMod.csproj" -c Release
if ($LASTEXITCODE -ne 0) { throw "mod build failed" }
$gameMods = "C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\mods\Sts2TasMod"
New-Item -ItemType Directory -Force -Path $gameMods | Out-Null
$dll = Join-Path $PWD "bridge\Sts2TasMod\bin\Release\net9.0\Sts2TasMod.dll"
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq "CN=Sts2TasMod" } | Select-Object -First 1
if (-not $cert) {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Sts2TasMod" -CertStoreLocation Cert:\CurrentUser\My
    $cer = Join-Path $env:TEMP "Sts2TasMod.cer"
    Export-Certificate -Cert $cert -FilePath $cer | Out-Null
    certutil -user -addstore TrustedPublisher $cer | Out-Null
}
Set-AuthenticodeSignature -FilePath $dll -Certificate $cert | Out-Null
Copy-Item $dll $gameMods -Force
Copy-Item "bridge\Sts2TasMod\Sts2TasMod.json" $gameMods -Force
$destDll = Join-Path $gameMods "Sts2TasMod.dll"
Set-AuthenticodeSignature -FilePath $destDll -Certificate $cert | Out-Null
Unblock-File $destDll -ErrorAction SilentlyContinue

$taskGame = "STS2TasLaunch"
$trGame = "cmd.exe /c start steam://rungameid/2868840"
schtasks /Create /TN $taskGame /TR $trGame /SC ONCE /ST 23:59 /F /IT | Out-Null
schtasks /Run /TN $taskGame | Out-Null

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
if (-not $opened) { throw "named pipe sts2-tas did not appear" }
Write-Output "pipe attached"

New-Item -ItemType Directory -Force -Path "models" | Out-Null
$runlive = Join-Path $Repo "scripts\windows-architect-runlive.ps1"
$taskTas = "STS2TasPlay"
$trTas = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runlive`""
Write-Output "=== start TAS in console session ==="
schtasks /Create /TN $taskTas /TR $trTas /SC ONCE /ST 23:59 /F /IT | Out-Null
schtasks /Run /TN $taskTas | Out-Null
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
