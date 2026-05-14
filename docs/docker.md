# Docker

## Build

macOS, Linux, Windows PowerShell 모두 같은 이미지 이름을 사용합니다.
이미지는 Python 3.14 slim 런타임을 기준으로 빌드합니다.

```bash
docker build -t sts2-tas:local .
docker run --rm sts2-tas:local --help
```

## Windows PowerShell

Docker Desktop에서 Linux containers 모드를 사용합니다. 현재 프로젝트 폴더를 `/workspace`로 mount하고, 입력 screenshot과 JSONL/model 파일은 volume 안에서 읽고 씁니다.

```powershell
docker build -t sts2-tas:local .
docker run --rm -v "${PWD}:/workspace" sts2-tas:local --help
```

예시:

```powershell
docker run --rm -v "${PWD}:/workspace" sts2-tas:local capture `
  --screenshot data/reward.png `
  --out data/steps.jsonl `
  --game-version 0.105.1 `
  --branch beta `
  --character ironclad `
  --ascension 0 `
  --floor 1 `
  --deck strike,bash `
  --relics burning_blood `
  --hp 70 `
  --gold 99
```

## Runtime Boundary

The container runs the CLI and model code. It does not capture the Windows desktop or click the game window. For live vision, capture screenshots on the host and pass those files into the container through a volume.

The image does not install the Tesseract binary or language packs. Use `--ocr-fixture` in the container, or run `--ocr-provider tesseract` on a host where Tesseract and the required English/Korean language data are installed.

Generated datasets and models should stay outside the image:

- `data/*.jsonl`
- `data/*.png`
- `models/*.pt`

## Remote execution via Tailscale SSH

현재 확인된 Windows 실행 노드는 Tailscale IP `100.71.5.113`, SSH alias `sts2-windows`, Windows 계정 `samsepi0l\steep`입니다. Tailscale은 사설 네트워크 경로만 제공하고, 로그인/권한은 Windows OpenSSH와 SSH key가 처리합니다. 따라서 Tailscale ping이 되어도 TCP 22와 SSH 인증을 별도로 확인해야 합니다.

Mac SSH client 설정:

```sshconfig
Host sts2-windows
    HostName 100.71.5.113
    User steep
    Port 22
    IdentityFile ~/.ssh/sts2_windows_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
```

연결 확인:

```bash
tailscale ping --timeout=5s 100.71.5.113
nc -vz -G 5 100.71.5.113 22
ssh sts2-windows 'powershell -NoProfile -Command "$env:COMPUTERNAME; whoami"'
```

확인된 정상 응답은 host `SAMSEPI0L`, user `samsepi0l\steep`입니다. RDP `3389`는 이 경로의 필수 조건이 아니며, 마지막 확인에서는 timeout이었습니다.

Windows OpenSSH server 준비:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

일반 사용자 key는 `C:\Users\steep\.ssh\authorized_keys`에 둡니다.

```powershell
$pub = '<mac ~/.ssh/sts2_windows_ed25519.pub content>'
$sshDir = Join-Path $env:USERPROFILE '.ssh'
$ak = Join-Path $sshDir 'authorized_keys'
New-Item -ItemType Directory -Force $sshDir | Out-Null
Set-Content -Path $ak -Value $pub -Encoding ascii
icacls $sshDir /inheritance:r /grant "$($env:USERNAME):(OI)(CI)F"
icacls $ak /inheritance:r /grant "$($env:USERNAME):F"
Restart-Service sshd
```

계정이 local Administrators 그룹이면 Windows OpenSSH가 사용자 `authorized_keys` 대신 `C:\ProgramData\ssh\administrators_authorized_keys`를 요구할 수 있습니다.

```powershell
$adminAk = 'C:\ProgramData\ssh\administrators_authorized_keys'
Set-Content -Path $adminAk -Value $pub -Encoding ascii
icacls $adminAk /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F'
Restart-Service sshd
```

원격 repo 실행은 OneDrive/Desktop checkout보다 별도 실행 디렉터리 `C:\Users\steep\sts2-tas-run`을 사용합니다. OneDrive 아래 `.venv`는 `uv trampoline failed to spawn Python child process` / `untrusted mount point (os error 448)`가 발생할 수 있습니다.

```powershell
cd C:\Users\steep\sts2-tas-run
$env:UV_PYTHON_INSTALL_DIR = 'C:\Users\steep\.local\uv-python'
$env:UV_CACHE_DIR = 'C:\Users\steep\.local\uv-cache'
$env:UV_LINK_MODE = 'copy'
uv sync --extra dev
.\.venv\Scripts\sts2-tas.exe --help
.\.venv\Scripts\pytest.exe tests\test_windowing.py tests\test_input_backend.py -q
```

마지막 확인 결과는 `31 passed in 9.48s`였습니다.

SSH service session은 Windows SessionId `0`에서 실행되므로 실제 desktop capture/input 경로가 아닙니다. 직접 SSH에서 `ImageGrab.grab()`은 `OSError: screen grab failed`가 날 수 있고, desktop window enumeration도 interactive session window를 보지 못할 수 있습니다. 실제 게임 화면 테스트는 로그인된 Windows interactive session에서 직접 실행하거나, `Interactive` scheduled task로 실행합니다. scheduled task는 `-WindowStyle Hidden`으로 실행해 PowerShell 콘솔 창이 게임 화면 캡처와 클릭 좌표를 가리지 않게 합니다.

```powershell
$taskName = 'STS2TASRemoteSmoke'
$script = 'C:\Users\steep\sts2-tas-run\remote-smoke\hidden-smoke.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$principal = New-ScheduledTaskPrincipal -UserId 'samsepi0l\steep' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
Start-ScheduledTask -TaskName $taskName
```

interactive task에서 확인된 게임 process는 `SlayTheSpire2`, SessionId는 `1`이었습니다. borderless/no-title 상태에서는 `MainWindowTitle`과 `MainWindowHandle`이 비어 있을 수 있으므로 `--target-process SlayTheSpire2`를 사용합니다. Windows target guard는 `EnumWindows`/`GetWindowThreadProcessId`로 해당 process의 top-level visible window를 다시 찾고, 빈 title과 bounds를 입력 직전 재검증합니다. 이 경로에서는 `ImageGrab.grab()`이 `1920x1080` capture를 만들고 target window metadata와 click plan을 출력합니다.

```powershell
.\.venv\Scripts\sts2-tas.exe live-step `
  --screenshot-out remote-smoke\interactive-live.png `
  --ocr-provider tesseract `
  --ocr-language eng+kor `
  --tessdata-dir remote-smoke\tessdata `
  --ocr-psm 12 `
  --choice pick:strike `
  --input-log remote-smoke\inputs.jsonl `
  --target-process SlayTheSpire2 `
  --game-version 0.105.1 `
  --branch beta `
  --character ironclad `
  --ascension 0 `
  --floor 1 `
  --hp 70 `
  --gold 99
```

실제 클릭은 dry-run의 target window metadata, screenshot crop, input plan이 맞는 것을 확인한 뒤에만 `--input-backend native --execute`를 추가합니다. Windows PowerShell 5.1의 `Set-Content -Encoding UTF8`로 만든 fixture JSON은 UTF-8 BOM이 붙을 수 있으며, CLI의 fixture/ack sequence loader는 이 BOM을 허용합니다.

Tesseract OCR은 Windows host에 설치해야 합니다.

```powershell
winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
$env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
tesseract --version
tesseract --list-langs
```

관리자 권한 없이 language pack을 보강해야 하면 실행 디렉터리 안에 tessdata를 둡니다.

```powershell
$tessdata = 'C:\Users\steep\sts2-tas-run\remote-smoke\tessdata'
New-Item -ItemType Directory -Force $tessdata | Out-Null
Copy-Item 'C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata' $tessdata -Force
Invoke-WebRequest `
  -Uri 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/kor.traineddata' `
  -OutFile (Join-Path $tessdata 'kor.traineddata')
.\.venv\Scripts\sts2-tas.exe parse-screen `
  --screenshot remote-smoke\interactive-live.png `
  --ocr-provider tesseract `
  --ocr-language eng+kor `
  --tessdata-dir $tessdata `
  --ocr-psm 12 `
  --out remote-smoke\parsed.json
```

마지막 확인된 기본 설치는 `v5.4.0.20240606`, language는 `eng`, `osd`였습니다. `kor.traineddata`는 host tessdata 또는 `--tessdata-dir` 경로에 있어야 `--ocr-language eng+kor`가 fixture 없이 동작합니다. 실제 게임 UI처럼 sparse text가 많은 화면은 `--ocr-psm 12`가 기본 page segmentation보다 안정적입니다.

## Windows Executable

Docker is not required when you only need a local Windows CLI executable. On Windows PowerShell, run:

```powershell
.\scripts\build-windows-exe.ps1
.\dist\sts2-tas.exe --help
```

The same build runs in GitHub Actions under `Build Windows Executable` and uploads `dist/sts2-tas.exe` as the `sts2-tas-windows-x64` artifact.
