# Documentation Index

- [Architecture](architecture.md): 데이터 흐름, CLI 범위, target window 감지, live-step/live-learn-loop 캡처/추천/입력 안전 경계.
- [Docker](docker.md): macOS/Linux/Windows Docker 실행법.
- [Implemented work](implemented-work.md): 현재 구현된 CLI, schema, recognition, ML, automation, runtime, verification 범위.
- [V1 gaps](v1-gaps.md): 2026-05-14 critical improvement review 기준 P0/P1 누락 범위와 수용 기준.
- Windows executable: `scripts/build-windows-exe.ps1`과 `.github/workflows/windows-exe.yml`이 `dist/sts2-tas.exe` / `sts2-tas-windows-x64` artifact를 만든다.

## MVP Scope

- 포함: 색상 fixture 감지, OCR fixture/Tesseract provider, 영어/한국어 시작 메뉴·모드·캐릭터·카드·유물·terminal/restart 식별, OCR text 기반 live state extractor, GameStep JSONL, 라벨링, PyTorch entity/action ranker 학습, 추천 CLI, live path에 연결된 state-derived legal action generator, 단일 live-step 자동화, transition acknowledgement fixture 경계, 반복 live-learn-loop 수집/재학습/episode 기록/terminal return 전파, dry-run/jsonl/native 입력 계획, macOS/Windows target window 좌표 변환, Windows native click, save backup/restore, save-state branch-and-bound 함수, seed episode 평가와 baseline 비교.
- 제외: Steam/Godot 내부 상태 직접 읽기, 온라인 co-op, Steam Leaderboards 자동화, neural RL 학습.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

Python 3.14 로컬 체크아웃에서 `.venv` editable install이 `sts2_tas`를 import하지 못하면 `PYTHONPATH=src`를 붙여 실행한다. 네트워크/빌드 의존성이 가능한 환경에서는 `uv run --no-editable ...`로 package install을 강제할 수 있다.
