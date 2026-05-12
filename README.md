# StS2 TAS

Slay the Spire 2 화면 인식 기반 TAS 학습 MVP입니다.

현재 범위는 실제 자동 클릭이 아니라 카드 보상/유물 선택 상황을 기록하고, 캐릭터별 supervised 모델로 `pick` 또는 `skip` 추천을 재현 가능하게 만드는 것입니다.

## Quick Start

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
uv run sts2-tas capture --screenshot reward.png --out data/snapshots.jsonl --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --deck strike,bash --relics burning_blood --hp 70 --gold 99
uv run sts2-tas label --dataset data/snapshots.jsonl --index 0 --choice pick:card_1
uv run sts2-tas train --dataset data/snapshots.jsonl --model models/ironclad.joblib --character ironclad
uv run sts2-tas recommend --model models/ironclad.joblib --snapshot query.json
```

## Docs

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
