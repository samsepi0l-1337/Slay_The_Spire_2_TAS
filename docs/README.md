# Documentation Index

- [Architecture](architecture.md): 데이터 흐름, trajectory schema, evaluation CLI, target window 감지, live-step/live-learn-loop 캡처/추천/입력 안전 경계.
- [Docker and Windows local execution](docker.md): Docker 보조 실행법, Windows 로컬 interactive session 기준의 live loop, Tailscale SSH 보조 경계.
- [Implemented work](implemented-work.md): 현재 구현된 CLI, schema, recognition, ML, automation, runtime, verification 범위.
- [V1 gaps](v1-gaps.md): 2026-05-14 critical improvement review 기준 P0/P1 누락 범위와 수용 기준.
- Windows executable: `scripts/build-windows-exe.ps1`(PyInstaller `--collect-all torch`)와 `.github/workflows/windows-exe.yml`이 `dist/sts2-tas.exe` / `sts2-tas-windows-x64` artifact를 만들고, CI에서 `tests/fixtures/ml-train-smoke.jsonl`로 `train` 한 번을 실행해 동결 exe의 PyTorch 경로를 스모크한다.

## MVP Scope

- 포함: 색상 fixture 감지, calibrated CV/OCR region filtering, OCR fixture/Tesseract provider, OCR token report, 영어/한국어 시작 메뉴·모드·캐릭터·카드·유물·terminal/restart 식별, OCR text 기반 live state extractor와 field confidence fail-closed gate, GameStep/TrajectoryStep JSONL, label_source 분리, reward/return-aware value target, 라벨링, PyTorch entity/action ranker 학습, 추천/evaluate-model/evaluate-play CLI, live path에 연결된 combat/card/map/shop/event/rest state-derived legal action generator, combat target multi-click 입력 계획, 단일 live-step 자동화, live frame polling 기반 retry/transition acknowledgement, Windows 로컬 interactive session의 반복 live-learn-loop 수집/재학습/episode/failure/trajectory 기록/terminal return 전파, dry-run/jsonl/native 입력 계획, macOS/Windows target window 좌표 변환, Windows native click, save backup/restore, save-state branch-and-bound/MCTS 함수, branch outcome scorer, seed episode 평가와 baseline 비교.
- 제외: Steam/Godot 내부 상태 직접 읽기, 온라인 co-op, Steam Leaderboards 자동화, neural RL 학습.

## Current Diagnosis

현재 checkout에서 간헐 오류처럼 보이는 현상은 먼저 로컬 regression과 실행 환경 경계를 분리해 봐야 한다. 최근 확인된 로컬 실패는 `live_learning.py`의 JSONL preflight가 실패 경로에서도 파일을 만들어 dataset append 차단 계약을 깨는 문제와, `step_factory.py`의 shop `player.character_resource.gold` required-field 처리 때문에 `None` resource와 confidence gate가 충돌하는 문제다.

실제 게임 실행 문제는 Windows 로컬 interactive session을 기준으로 진단한다. Mac SSH, Docker, Windows SSH service session은 게임 화면 capture/click의 기준 환경이 아니며, Tesseract 설치, `eng+kor` language data, target process 이름, screen capture 권한, `--ack-live-poll`/`--failure-log` 설정을 별도로 확인한다.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

Python 3.14 로컬 체크아웃에서 `.venv` editable install이 `sts2_tas`를 import하지 못하면 `PYTHONPATH=src`를 붙여 실행한다. 네트워크/빌드 의존성이 가능한 환경에서는 `uv run --no-editable ...`로 package install을 강제할 수 있다.
