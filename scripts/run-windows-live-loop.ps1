param(
    [string]$WorkDir = "C:\Users\steep\sts2-tas-run",
    [string]$TaskName = "STS2TASLiveLoop",
    [string]$TargetProcess = "SlayTheSpire2",
    [string]$DataDir = "data\windows-live-loop",
    [string]$StopFile = "remote-smoke\stop-live-loop.flag",
    [string]$OcrLanguage = "eng+kor",
    [string]$TesseractBinary = "C:\Program Files\Tesseract-OCR\tesseract.exe",
    [string]$TessdataDir = "remote-smoke\tessdata",
    [int]$OcrPsm = 12,
    [int]$AckMaxRetries = 2,
    [string]$GameVersion = "0.105.1",
    [string]$Branch = "beta",
    [string]$Character = "ironclad",
    [int]$Ascension = 0,
    [int]$Floor = 1,
    [int]$Hp = 70,
    [int]$Gold = 0,
    [int]$TrainEvery = 10,
    [int]$Epochs = 1,
    [int]$BatchSize = 64,
    [string]$Device = "cpu",
    [string]$ModelOut = "models\windows-live-loop.pt",
    [string]$Sts2Exe = "",
    [string]$UserId = "",
    [ValidateSet("Highest", "Limited")]
    [string]$RunLevel = "Highest",
    [switch]$Run,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

function Resolve-WorkspacePath([string]$PathValue) {
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $WorkDir $PathValue
}

function Quote-Argument([string]$Value) {
    return '"' + $Value.Replace('"', '\"') + '"'
}

$WorkDir = [System.IO.Path]::GetFullPath($WorkDir)
$StopFile = Resolve-WorkspacePath $StopFile
$DataDir = Resolve-WorkspacePath $DataDir
$TessdataDir = Resolve-WorkspacePath $TessdataDir
$ModelOut = Resolve-WorkspacePath $ModelOut
if (-not [string]::IsNullOrWhiteSpace($Sts2Exe)) {
    if ([System.IO.Path]::IsPathRooted($Sts2Exe)) {
        $Sts2Exe = [System.IO.Path]::GetFullPath($Sts2Exe)
    } else {
        $Sts2Exe = [System.IO.Path]::GetFullPath((Join-Path $WorkDir $Sts2Exe))
    }
}

if ($Stop) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $StopFile) | Out-Null
    Set-Content -Path $StopFile -Value "stop" -Encoding ascii
    Write-Output "stop-file: $StopFile"
    return
}

if ($Run) {
    Set-Location $WorkDir
    New-Item -ItemType Directory -Force $DataDir | Out-Null
    New-Item -ItemType Directory -Force (Split-Path -Parent $ModelOut) | Out-Null
    $useExe = -not [string]::IsNullOrWhiteSpace($Sts2Exe)
    if ($useExe -and -not (Test-Path $Sts2Exe)) {
        throw "Sts2Exe not found: $Sts2Exe"
    }
    if (-not $useExe) {
        $env:PYTHONPATH = "src"
        $python = Join-Path $WorkDir ".venv\Scripts\python.exe"
        if (-not (Test-Path $python)) {
            throw "Python venv not found (use -Sts2Exe for packaged exe): $python"
        }
    }
    $liveArgs = @(
        "live-learn-loop",
        "--screenshot-out", (Join-Path $DataDir "live.png"),
        "--ocr-provider", "tesseract",
        "--ocr-language", $OcrLanguage,
        "--tesseract-binary", $TesseractBinary,
        "--tessdata-dir", $TessdataDir,
        "--ocr-psm", "$OcrPsm",
        "--dataset", (Join-Path $DataDir "dataset.jsonl"),
        "--trajectory-out", (Join-Path $DataDir "trajectory.jsonl"),
        "--episodes-out", (Join-Path $DataDir "episodes.jsonl"),
        "--failure-log", (Join-Path $DataDir "failures.jsonl"),
        "--input-log", (Join-Path $DataDir "inputs.jsonl"),
        "--policy", "first-legal",
        "--ack-live-poll",
        "--ack-max-retries", "$AckMaxRetries",
        "--target-process", $TargetProcess,
        "--input-backend", "native",
        "--execute",
        "--stop-file", $StopFile,
        "--train-every", "$TrainEvery",
        "--model-out", $ModelOut,
        "--epochs", "$Epochs",
        "--batch-size", "$BatchSize",
        "--device", $Device,
        "--game-version", $GameVersion,
        "--branch", $Branch,
        "--character", $Character,
        "--ascension", "$Ascension",
        "--floor", "$Floor",
        "--hp", "$Hp",
        "--gold", "$Gold"
    )
    $logPath = Join-Path $DataDir "live-loop.log"
    if ($useExe) {
        & $Sts2Exe @liveArgs *> $logPath
    } else {
        & $python -m sts2_tas @liveArgs *> $logPath
    }
    exit $LASTEXITCODE
}

Set-Location $WorkDir
New-Item -ItemType Directory -Force $DataDir | Out-Null
New-Item -ItemType Directory -Force (Split-Path -Parent $StopFile) | Out-Null
Remove-Item -Force $StopFile -ErrorAction SilentlyContinue

$scriptPath = $PSCommandPath
$argumentParts = @(
    "-WindowStyle Hidden",
    "-NoProfile",
    "-ExecutionPolicy Bypass",
    "-File", (Quote-Argument $scriptPath),
    "-Run",
    "-WorkDir", (Quote-Argument $WorkDir),
    "-TaskName", (Quote-Argument $TaskName),
    "-TargetProcess", (Quote-Argument $TargetProcess),
    "-DataDir", (Quote-Argument $DataDir),
    "-StopFile", (Quote-Argument $StopFile),
    "-OcrLanguage", (Quote-Argument $OcrLanguage),
    "-TesseractBinary", (Quote-Argument $TesseractBinary),
    "-TessdataDir", (Quote-Argument $TessdataDir),
    "-OcrPsm", $OcrPsm,
    "-AckMaxRetries", $AckMaxRetries,
    "-GameVersion", (Quote-Argument $GameVersion),
    "-Branch", (Quote-Argument $Branch),
    "-Character", (Quote-Argument $Character),
    "-Ascension", $Ascension,
    "-Floor", $Floor,
    "-Hp", $Hp,
    "-Gold", $Gold,
    "-TrainEvery", $TrainEvery,
    "-Epochs", $Epochs,
    "-BatchSize", $BatchSize,
    "-Device", (Quote-Argument $Device),
    "-ModelOut", (Quote-Argument $ModelOut)
)
if (-not [string]::IsNullOrWhiteSpace($Sts2Exe)) {
    $argumentParts += @("-Sts2Exe", (Quote-Argument $Sts2Exe))
}
$arguments = $argumentParts -join " "

if ([string]::IsNullOrWhiteSpace($UserId)) {
    $UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel $RunLevel
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
Write-Output "task: $TaskName"
Write-Output "stop: powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -Stop -WorkDir $WorkDir -StopFile $StopFile"
Write-Output "log: $(Join-Path $DataDir 'live-loop.log')"
