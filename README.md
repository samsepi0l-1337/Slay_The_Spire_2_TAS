# StS2 TAS

Slay the Spire 2 화면 인식 기반 TAS 학습/자동화 MVP입니다.

현재 범위는 카드 보상/유물 선택 상황을 OCR로 파싱하고, 캐릭터별 supervised 모델로 `pick` 또는 `skip` 추천을 재현 가능하게 만들며, 기본 dry-run 자동화와 seed별 평가 로그를 제공합니다. 실제 입력 실행은 `--execute`가 있을 때만 동작하고, 기본 입력 백엔드는 JSONL 기록입니다.

## Quick Start

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
uv run sts2-tas capture --screenshot reward.png --out data/snapshots.jsonl --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --deck strike,bash --relics burning_blood --hp 70 --gold 99
uv run sts2-tas label --dataset data/snapshots.jsonl --index 0 --choice pick:card_1
uv run sts2-tas train --dataset data/snapshots.jsonl --model models/ironclad.joblib --character ironclad
uv run sts2-tas recommend --model models/ironclad.joblib --snapshot query.json
uv run sts2-tas parse-screen --screenshot reward.png --ocr-fixture ocr.json --out parsed.json
uv run sts2-tas parse-screen --screenshot reward.png --ocr-provider tesseract --ocr-language eng+kor --out parsed.json
uv run sts2-tas act --snapshot query.json --choice pick:strike --input-log inputs.jsonl
uv run sts2-tas act --snapshot query.json --choice pick:strike --input-log inputs.jsonl --input-backend native --execute
uv run sts2-tas live-step --screenshot-out live.png --ocr-provider tesseract --choice pick:strike --input-log inputs.jsonl --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-step --capture-fixture reward.png --ocr-fixture ocr.json --model models/ironclad.joblib --input-log inputs.jsonl --execute --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas run-loop --seeds 7,8 --capture-fixture reward.png --ocr-fixture ocr.json --episodes-out episodes.jsonl --max-steps 1
uv run sts2-tas evaluate-seeds --episodes episodes.jsonl --out summary.json
```

## Docker

```bash
docker build -t sts2-tas:local .
docker run --rm sts2-tas:local --help
```

Windows에서는 Docker Desktop의 Linux containers 모드에서 실행하고, screenshot/data/model 폴더를 volume으로 연결합니다. 자세한 명령은 [docs/docker.md](docs/docker.md)를 보세요.

## Docs

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/docker.md](docs/docker.md)
- [docs/v1-gaps.md](docs/v1-gaps.md)
