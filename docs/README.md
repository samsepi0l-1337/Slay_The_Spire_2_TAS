# Documentation Index

- [Architecture](architecture.md): 데이터 흐름, CLI 범위, target window 감지, live-step 캡처/추천/입력 안전 경계.
- [Docker](docker.md): macOS/Linux/Windows Docker 실행법.
- [Implemented work](implemented-work.md): 현재 구현된 CLI, schema, recognition, ML, automation, runtime, verification 범위.
- [v1 gaps](v1-gaps.md): 구현된 live vision 범위와 아직 제외한 직접 내부 상태 접근.
- Windows executable: `scripts/build-windows-exe.ps1`과 `.github/workflows/windows-exe.yml`이 `dist/sts2-tas.exe` / `sts2-tas-windows-x64` artifact를 만든다.

## MVP Scope

- 포함: 색상 fixture 감지, OCR fixture/Tesseract provider, 영어/한국어 카드·유물 식별, GameStep JSONL, 라벨링, PyTorch entity/action ranker 학습, 추천 CLI, 단일 live-step 자동화, dry-run/jsonl/native 입력 계획, macOS target window 좌표 변환, save backup/restore, seed episode 평가.
- 제외: Steam/Godot 내부 상태 직접 읽기, 온라인 co-op, Steam Leaderboards 자동화, neural RL 학습.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

Python 3.14 로컬 체크아웃에서 `.venv` editable install이 `sts2_tas`를 import하지 못하면 `PYTHONPATH=src`를 붙여 실행한다. 네트워크/빌드 의존성이 가능한 환경에서는 `uv run --no-editable ...`로 package install을 강제할 수 있다.
