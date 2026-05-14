# StS2 TAS

Slay the Spire 2 화면 인식 기반 TAS 학습/자동화 MVP입니다.

현재 범위는 최초 시작 메뉴, Continue/계속, 싱글 플레이/모드/캐릭터 선택, 카드 보상/유물 선택, combat/map/shop/event/rest OCR state, game over/clear 재시작 화면을 OCR로 파싱하고, gameplay `GameStep`/`TrajectoryStep` JSONL과 PyTorch entity/action ranker로 선택지를 학습/추천하는 것입니다. 실제 입력 실행은 `--execute`가 있을 때만 동작하고, 기본 입력 백엔드는 JSONL 기록입니다. macOS/Windows에서는 `live-step --screenshot-out --target-process "Slay the Spire 2"`로 target window crop을 만들고, 같은 실행 안에서 window-relative 좌표를 native 입력 전 재검증합니다. `live-learn-loop --model`은 기본적으로 모델 선택을 supervised label로 저장하지 않으며, 실험적으로 자기 라벨을 허용할 때만 `--allow-model-self-labels`를 사용합니다.

## Quick Start

Python 3.14 이상에서 실행합니다.

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
uv run sts2-tas capture --screenshot reward.png --out data/steps.jsonl --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --deck strike,bash --relics burning_blood --hp 70 --max-hp 80 --block 0 --energy 3 --turn 1 --gold 99
uv run sts2-tas label --dataset data/steps.jsonl --index 0 --choice pick_card:card_1
uv run sts2-tas train --dataset data/steps.jsonl --model models/ironclad.pt --character ironclad --epochs 30 --batch-size 128 --device auto
uv run sts2-tas recommend --model models/ironclad.pt --step query.json
uv run sts2-tas evaluate-model --eval-dataset data/steps.jsonl --model models/ironclad.pt --character ironclad --out model-eval.json
uv run sts2-tas parse-screen --screenshot reward.png --ocr-fixture ocr.json --out parsed.json
uv run sts2-tas parse-screen --screenshot reward.png --ocr-provider tesseract --ocr-language eng+kor --tesseract-binary tesseract --tessdata-dir tessdata --ocr-psm 12 --out parsed.json
uv run sts2-tas parse-screen --screenshot reward.png --ocr-provider tesseract --region-calibration regions.json --out parsed.json
uv run sts2-tas act --step query.json --choice pick_card:strike --input-log inputs.jsonl
uv run sts2-tas act --step query.json --choice pick_card:strike --input-log inputs.jsonl --input-backend native --execute
uv run sts2-tas live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike --input-log inputs.jsonl --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike --input-log inputs.jsonl --target-process "Slay the Spire 2" --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike --input-log inputs.jsonl --target-process "Slay the Spire 2" --input-backend native --execute --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike --input-log inputs.jsonl --ack-live-poll --ack-max-retries 2 --execute --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-step --capture-fixture reward.png --ocr-fixture ocr.json --model models/ironclad.pt --input-log inputs.jsonl --execute --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-learn-loop --screenshot-out live.png --ocr-provider tesseract --model models/ironclad.pt --dataset data/live.jsonl --input-log inputs.jsonl --max-steps 10 --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-learn-loop --screenshot-out live.png --ocr-provider tesseract --model models/ironclad.pt --dataset data/live.jsonl --trajectory-out data/trajectory.jsonl --failure-log data/failures.jsonl --ack-live-poll --ack-max-retries 2 --input-log inputs.jsonl --execute --max-steps 10 --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-learn-loop --screenshot-out live.png --ocr-provider tesseract --model models/ironclad.pt --dataset data/live.jsonl --episodes-out data/episodes.jsonl --input-log inputs.jsonl --max-steps 50 --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas live-learn-loop --screenshot-out live.png --ocr-provider tesseract --policy first-legal --dataset data/live.jsonl --episodes-out data/episodes.jsonl --failure-log data/failures.jsonl --input-log inputs.jsonl --stop-file stop-live-loop.flag --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
uv run sts2-tas run-loop --seeds 7,8 --victory-seeds 8 --capture-fixture reward.png --ocr-fixture ocr.json --episodes-out episodes.jsonl --max-steps 1
uv run sts2-tas evaluate-seeds --episodes episodes.jsonl --out summary.json
uv run sts2-tas evaluate-seeds --episodes candidate.jsonl --baseline rule-baseline.jsonl --out comparison.json
uv run sts2-tas evaluate-play --episodes episodes.jsonl --out play-eval.json
```

실제 학습용 row는 `--state-json`으로 player/card/relic/potion/monster/path/shop/event/rest 상태를 함께 넣는 것을 권장합니다. CLI flag로 주지 않은 값은 `ObservationQuality.missing_fields`에 남겨 모델 입력 품질을 추적합니다. OCR state에서 context별 필수 field가 없거나 `field_confidence < 0.60`이면 `live-step`/`live-learn-loop`는 입력과 dataset append를 중단합니다. 기존 `GameStep` JSONL은 계속 읽히며, `label_source`가 없으면 `human`으로 처리됩니다. 기본 학습은 `human`/`search`/`heuristic` label만 사용하고 model self/shadow row는 제외합니다.

로컬 Python 3.14 editable install이 `sts2_tas`를 import하지 못하는 환경에서는 `.venv` hidden flag를 정리한 뒤 다시 실행합니다. 임시 우회가 필요하면 `PYTHONPATH=src uv run ...` 또는 `uv run --no-editable ...`로 실행할 수 있습니다.

`--target-process --input-backend native --execute` 조합은 실제 OS 입력을 보내는 production 경로입니다. Windows borderless/no-title 게임 창은 process name인 `SlayTheSpire2`로 지정하면 EnumWindows 기반 target guard가 빈 title과 window bounds를 재검증합니다. 먼저 같은 명령에서 `--input-backend native --execute`를 빼고 dry-run/JSONL 계획과 target window metadata가 맞는지 확인합니다.

`live-learn-loop`는 `live-step`과 같은 capture/OCR/action 선택 경계를 반복합니다. Gameplay 화면은 combat/card reward/relic choice/map/shop/event/rest이며, `--choice` 라벨, `--policy first-legal` heuristic 라벨, 또는 `--allow-model-self-labels`를 명시한 실험에서만 `chosen_action_id`가 채워진 `GameStep`을 JSONL dataset에 누적합니다. `--execute`로 gameplay label/model action을 보낸 경우에는 transition ack가 `changed`일 때만 `GameStep`과 `TrajectoryStep`을 append합니다. ack가 없거나 `no_op`/`timeout`/controller error/fail-closed perception/preflight failure이면 `--failure-log` JSONL에 실패만 기록하고 dataset/trajectory append는 하지 않습니다. JSONL input backend는 transition ack가 `changed`일 때만 input log를 commit합니다. 메뉴/모드/캐릭터/재시작 화면은 학습 row로 저장하지 않고 입력 계획만 만들며, terminal 화면은 `--episodes-out`에 승패 요약을 남긴 뒤 `New Run` 액션으로 다음 run을 시작합니다. fixture JSON은 Windows PowerShell 5.1의 UTF-8 BOM이 있어도 읽을 수 있습니다. terminal return 전파 후에는 모델을 한 번 더 재학습해 최종 reward가 반영된 row를 저장 모델에 반영하고, 같은 terminal frame 반복은 steps=0 episode row로 중복 기록하지 않습니다. `--max-steps` 없이 실행하면 사용자가 중단할 때까지 반복하고, `KeyboardInterrupt` 또는 `--stop-file` 감지는 traceback 대신 summary JSON으로 종료합니다. `--screenshot-out live.png`는 반복마다 `live-000001.png`처럼 충돌 없는 파일명을 사용합니다.

OCR text가 `HP 65/80`, `Energy 3/3`, `Hand Strike cost 1 attack`, `Monster Jaw Worm 30/44 block 3 attack 7x1`, `Path node-a ...`, `Shop item Strike card price 75`, `Leave shop`, `Event option Take gold`, `Rest option Smith` 같은 live state grammar를 포함하면 `live-step`/`live-learn-loop`는 이를 structured state로 병합하고 state-derived legal action generator에 연결합니다. 중복 shop/event label은 slot id로 분리하고, shop buy/remove action은 관측된 player gold가 price 이상일 때만 생성되며, `leave_shop`은 관측된 leave box가 있을 때만 legal action으로 생성합니다. Targeted combat action은 card source click 후 monster target click sequence로 계획되며, monster target box가 없으면 실행 계획을 만들지 않습니다. Combat `end_turn`은 Escape가 아니라 in-game turn 종료 단축키 `e` keypress로 계획합니다. `--region-calibration`은 card/relic/skip/menu region을 현재 resolution에 맞춰 scale해 OCR/CV 후보를 필터링합니다. `--ack-ocr-fixture`, `--ack-ocr-fixture-sequence`, `--ack-live-poll`은 입력 후 상태 변화 여부를 `changed`/`no_op`/`timeout`으로 리포트하고 retry가 필요한 경우 `--ack-max-retries` 범위에서 post-input frame만 다시 poll합니다. 같은 action input은 retry 중 재전송하지 않습니다. `--ack-max-retries`는 0 이상의 정수만 허용합니다. `evaluate-play`는 latency/timeout/misclick/illegal/candidate-recall 안전 지표가 빠진 episode row를 기본적으로 실패 지표로 계산하며, `--allow-missing-metrics`에서는 missing row 수를 리포트하고 missing candidate recall을 평균에서 제외합니다.

모델 선택을 supervised label로 재학습하는 실험은 `--allow-model-self-labels --train-every N --model-out models/ironclad.pt`를 함께 명시할 때만 사용합니다.

## Docker

```bash
docker build -t sts2-tas:local .
docker run --rm sts2-tas:local --help
```

Windows에서는 Docker Desktop의 Linux containers 모드에서 실행하고, screenshot/data/model 폴더를 volume으로 연결합니다. 자세한 명령은 [docs/docker.md](docs/docker.md)를 보세요.

Tailscale SSH로 Windows 실행 노드에 접속해 테스트할 때도 실행 경계는 같습니다. SSH는 파일 전송/빌드/interactive scheduled task 실행에 사용하고, 실제 게임 화면 capture/click은 로그인된 Windows interactive session에서 실행합니다. 연결 설정과 검증 명령은 [docs/docker.md#remote-execution-via-tailscale-ssh](docs/docker.md#remote-execution-via-tailscale-ssh)를 보세요.

Windows에서 장시간 실제 입력 loop를 hidden scheduled task로 실행하려면 [docs/docker.md#continuous-windows-live-loop](docs/docker.md#continuous-windows-live-loop)의 `scripts/run-windows-live-loop.ps1` 명령을 사용합니다.

## Windows Executable

Windows 실행 파일은 Windows runner 또는 Windows PowerShell에서 `scripts/build-windows-exe.ps1`로 빌드합니다.

```powershell
.\scripts\build-windows-exe.ps1
.\dist\sts2-tas.exe --help
.\dist\sts2-tas.exe live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike --input-log inputs.jsonl --target-process "Slay the Spire 2" --input-backend native --execute --game-version 0.105.1 --branch beta --character ironclad --ascension 0 --floor 1 --hp 70 --gold 99
```

GitHub Actions의 `Build Windows Executable` workflow도 같은 스크립트를 실행하고, `sts2-tas-windows-x64` artifact로 `dist/sts2-tas.exe`를 업로드합니다. 이 `.exe`는 CLI와 model/recommend 경로를 실행하는 패키지이며, Windows native backend는 PowerShell/user32 기반 target-window detection, click, SendKeys keypress를 지원합니다.

## Docs

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/docker.md](docs/docker.md)
- [docs/v1-gaps.md](docs/v1-gaps.md)
