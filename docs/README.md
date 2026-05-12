# Documentation Index

- [Architecture](architecture.md): 데이터 흐름, CLI 범위, live-step 캡처/추천/입력 안전 경계.
- [Docker](docker.md): macOS/Linux/Windows Docker 실행법.
- [v1 gaps](v1-gaps.md): 구현된 live vision 범위와 아직 제외한 직접 내부 상태 접근.

## MVP Scope

- 포함: 색상 fixture 감지, OCR fixture/Tesseract provider, 영어/한국어 카드·유물 식별, DecisionSnapshot JSONL, 라벨링, scikit-learn 학습, 추천 CLI, 단일 live-step 자동화, dry-run/jsonl 입력 계획, save backup/restore, seed episode 평가.
- 제외: Steam/Godot 내부 상태 직접 읽기, 온라인 co-op, Steam Leaderboards 자동화, neural RL 학습.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```
