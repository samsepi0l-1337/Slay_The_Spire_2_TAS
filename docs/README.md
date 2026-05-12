# Documentation Index

- [Architecture](architecture.md): 데이터 흐름, CLI 범위, 모델/인식 제약.

## MVP Scope

- 포함: 화면 fixture 기반 카드 보상/유물 선택 감지, DecisionSnapshot JSONL, 라벨링, scikit-learn 학습, 추천 CLI.
- 제외: 실제 게임 클릭 실행, 온라인 co-op, Steam Leaderboards 자동화, 강화학습.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```
