# Docker and Windows Local Execution

## Build

macOS, Linux, Windows PowerShell 모두 같은 이미지 이름을 사용합니다.
이미지는 Python 3.14 slim 런타임을 기준으로 빌드합니다.

## Windows local-first execution

이 프로젝트의 live TAS 경로는 Windows 로컬 interactive session에서 Slay the Spire 2 화면을 직접 보고, OCR 결과와 transition ack가 확인된 gameplay action만 ML dataset으로 누적하는 프로그램입니다. Mac에서 SSH로 Windows를 조종하는 구조가 핵심이 아닙니다.

권장 실행 기준:

- Windows desktop에 사용자가 로그인되어 있고 게임 창이 실제로 열려 있다.
- `live-learn-loop`는 Windows 로컬 PowerShell 또는 interactive scheduled task에서 실행한다.
- `--target-process SlayTheSpire2`, `--ack-live-poll`, `--failure-log`, `--input-backend native`, `--execute` 조합은 dry-run 검증 후에만 사용한다.
- Tesseract binary와 `eng+kor` language data는 Windows host에 설치한다.
- Mac/Tailscale SSH는 repo 동기화, 빌드, task 등록, 로그 회수에만 사용한다.
- Docker는 CLI/model/fixture 처리용이며 Windows desktop capture/click을 수행하지 않는다.

현재 실패 진단은 두 층으로 나눈다. 첫째, 로컬 unit test가 실패하면 live 실행 전 코드 회귀를 먼저 고친다. 최근 확인된 실패 유형은 JSONL preflight가 실패 경로에서도 dataset/trajectory 파일을 만들어 append 차단 계약을 깨는 문제와, shop 화면의 `player.character_resource.gold` required-field 처리에서 captured state와 OCR confidence gate가 충돌하는 문제다. 둘째, unit test가 green이어도 실제 게임에서는 OCR/Tesseract, target process, Windows session, screen capture 권한, transition ack 설정을 별도 확인한다.

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

## Tailscale SSH as a helper

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

Windows 로컬 실행 디렉터리는 OneDrive/Desktop checkout보다 별도 실행 디렉터리 `C:\Users\steep\sts2-tas-run`을 사용합니다. OneDrive 아래 `.venv`는 `uv trampoline failed to spawn Python child process` / `untrusted mount point (os error 448)`가 발생할 수 있습니다.
repo에는 `.python-version`을 `3.14.5`로 고정해 Windows SSH에서 `uv`가 `cpython-3.14-*` junction alias를 선택하지 않도록 한다.

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

SSH service session은 Windows SessionId `0`에서 실행되므로 실제 desktop capture/input 경로가 아닙니다. 직접 SSH에서 `ImageGrab.grab()`은 `OSError: screen grab failed`가 날 수 있고, desktop window enumeration도 interactive session window를 보지 못할 수 있습니다. 실제 게임 화면 테스트는 logged-in local interactive session에서 직접 실행하거나, 같은 로그인 세션의 `Interactive` scheduled task로 실행합니다. scheduled task의 `-WindowStyle Hidden`은 콘솔 창이 게임 화면 캡처와 클릭 좌표를 가리지 않게 하는 표시 방식일 뿐, SSH/service session을 acceptance 실행 환경으로 바꾸지 않습니다.

```powershell
$taskName = 'STS2TASRemoteSmoke'
$script = 'C:\Users\steep\sts2-tas-run\remote-smoke\hidden-smoke.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$principal = New-ScheduledTaskPrincipal -UserId 'samsepi0l\steep' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
Start-ScheduledTask -TaskName $taskName
```

interactive task에서 확인된 게임 process는 `SlayTheSpire2`, SessionId는 `1`이었습니다. borderless/no-title 상태에서는 `MainWindowTitle`과 `MainWindowHandle`이 비어 있을 수 있으므로 `--target-process SlayTheSpire2`를 사용합니다. Windows target guard는 `EnumWindows`/`GetWindowThreadProcessId`로 해당 process의 top-level visible window를 다시 찾고, 빈 title과 bounds를 입력 직전 재검증합니다. `--target-process`가 지정됐는데 visible top-level window를 찾지 못하면 전체 데스크톱을 OCR하지 않고 `target process window not found`로 실패합니다. 이 경로에서는 target window crop, target window metadata, click plan을 함께 확인합니다.

```powershell
.\.venv\Scripts\sts2-tas.exe live-step `
  --screenshot-out remote-smoke\interactive-live.png `
  --ocr-provider tesseract `
  --ocr-language eng+kor `
  --tesseract-binary 'C:\Program Files\Tesseract-OCR\tesseract.exe' `
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
  --tesseract-binary 'C:\Program Files\Tesseract-OCR\tesseract.exe' `
  --tessdata-dir $tessdata `
  --ocr-psm 12 `
  --out remote-smoke\parsed.json
```

마지막 확인된 기본 설치는 `v5.4.0.20240606`, language는 `eng`, `osd`였습니다. `kor.traineddata`는 host tessdata 또는 `--tessdata-dir` 경로에 있어야 `--ocr-language eng+kor`가 fixture 없이 동작합니다. PATH가 잡히지 않은 host에서는 `--tesseract-binary 'C:\Program Files\Tesseract-OCR\tesseract.exe'`로 binary를 직접 지정합니다. 실제 게임 UI처럼 sparse text가 많은 화면은 `--ocr-psm 12`가 기본 page segmentation보다 안정적입니다.

## Continuous Windows Live Loop

Windows logged-in local interactive session에서 게임 창이 열린 상태라면 `scripts/run-windows-live-loop.ps1`로 interactive scheduled task를 등록해 사용자가 멈출 때까지 실행할 수 있습니다. 이 wrapper는 `live-learn-loop`를 `--max-steps` 없이 실행하고, `--policy first-legal`, `--ack-live-poll`, `--target-process SlayTheSpire2`, `--input-backend native`, `--execute`, `--stop-file`을 함께 전달합니다. 승리 또는 게임 오버 terminal 화면에서 `New Run`/`다시 시작`이 인식되면 restart action을 클릭하고 다음 run으로 이어갑니다.

기본값은 `-RunLevel Highest`라 `Register-ScheduledTask`에 **관리자 권한**이 필요합니다. `Access is denied`가 나오면 PowerShell을 **관리자로 실행**한 뒤 같은 명령을 쓰거나, `-RunLevel Limited`로 등록을 낮춥니다(일부 환경에서 입력/포커스 동작이 달라질 수 있음).

```powershell
cd C:\Users\steep\sts2-tas-run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-windows-live-loop.ps1 `
  -WorkDir C:\Users\steep\sts2-tas-run `
  -TargetProcess SlayTheSpire2 `
  -DataDir data\windows-live-loop `
  -StopFile remote-smoke\stop-live-loop.flag `
  -TesseractBinary 'C:\Program Files\Tesseract-OCR\tesseract.exe' `
  -TessdataDir remote-smoke\tessdata
```

비관리자 세션에서 스케줄 등록만 막힐 때:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-windows-live-loop.ps1 `
  -WorkDir C:\Users\steep\sts2-tas-run -RunLevel Limited `
  -DataDir data\windows-live-loop -StopFile remote-smoke\stop-live-loop.flag
```

중단은 같은 checkout에서 stop file을 만들면 됩니다. hidden task는 다음 iteration 시작 시 이를 감지하고 summary JSON을 남기며 종료합니다.

```powershell
.\scripts\run-windows-live-loop.ps1 -Stop -StopFile remote-smoke\stop-live-loop.flag
```

wrapper가 내부에서 실행하는 핵심 CLI 형태는 아래와 같습니다.

```powershell
.\.venv\Scripts\python.exe -m sts2_tas live-learn-loop `
  --screenshot-out data\windows-live-loop\live.png `
  --ocr-provider tesseract `
  --ocr-language eng+kor `
  --tesseract-binary 'C:\Program Files\Tesseract-OCR\tesseract.exe' `
  --tessdata-dir remote-smoke\tessdata `
  --ocr-psm 12 `
  --dataset data\windows-live-loop\dataset.jsonl `
  --trajectory-out data\windows-live-loop\trajectory.jsonl `
  --episodes-out data\windows-live-loop\episodes.jsonl `
  --failure-log data\windows-live-loop\failures.jsonl `
  --input-log data\windows-live-loop\inputs.jsonl `
  --policy first-legal `
  --ack-live-poll `
  --ack-max-retries 2 `
  --target-process SlayTheSpire2 `
  --input-backend native `
  --execute `
  --stop-file remote-smoke\stop-live-loop.flag `
  --train-every 10 `
  --model-out models\windows-live-loop.pt `
  --epochs 1 `
  --batch-size 64 `
  --device cpu `
  --game-version 0.105.1 `
  --branch beta `
  --character ironclad `
  --ascension 0 `
  --floor 1 `
  --hp 70 `
  --gold 0
```

`--policy first-legal`은 trained model이 없는 상태에서도 legal action 중 첫 후보를 heuristic label로 저장합니다. 실게임 OCR이 로딩 화면이나 알 수 없는 partial frame을 반환하면 `--failure-log`에 `screen_parse_failed`를 남기고 다음 iteration으로 넘어갑니다. 모델 기반 선택으로 전환할 때는 `--policy first-legal` 대신 `--model models\...pt`와 필요 시 `--allow-model-self-labels`를 사용합니다.

## Windows Executable

Docker is not required when you only need a local Windows CLI executable. On Windows PowerShell, run:

```powershell
.\scripts\build-windows-exe.ps1
.\dist\sts2-tas.exe --help
```

`build-windows-exe.ps1`는 PyInstaller에 `--collect-all torch`를 넘겨 onefile `sts2-tas.exe` 안에 PyTorch DLL·확장·데이터를 함께 묶습니다. CI(`Build Windows Executable`)는 빌드 후 `tests/fixtures/ml-train-smoke.jsonl`로 `train` 한 번을 실행해 동결된 exe에서 실제 backward가 돌아가는지 확인합니다.

원격 머신에서 venv 대신 exe로 `live-learn-loop`(및 주기적 `train`)를 돌리려면 `scripts/run-windows-live-loop.ps1`에 `-Sts2Exe`로 exe 경로를 넘깁니다(작업 디렉터리 기준 상대 경로 또는 절대 경로).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-windows-live-loop.ps1 `
  -WorkDir C:\Users\steep\sts2-tas-run `
  -Sts2Exe dist\sts2-tas.exe `
  -TargetProcess SlayTheSpire2 `
  -DataDir data\windows-live-loop `
  -StopFile remote-smoke\stop-live-loop.flag
```

The same build runs in GitHub Actions under `Build Windows Executable` and uploads `dist/sts2-tas.exe` as the `sts2-tas-windows-x64` artifact.
