# Implemented Work

현재 구현된 기능과 검증 범위를 실제 코드 기준으로 정리한다. 제외 항목은 Safety Boundaries와 각 영역의 extension point에 함께 유지한다.

## CLI Commands

- `capture`: 색상 기반 화면 fixture를 감지해 unlabeled `GameStep` JSONL을 기록한다.
- `parse-screen`: screenshot과 OCR provider 결과를 catalog-matched option JSON으로 변환한다. `--region-calibration`으로 calibrated OCR region filtering을 적용할 수 있다.
- `capture-live`: OCR 결과를 `GameStep` JSONL로 저장한다. `--region-calibration`을 같은 parse path에 전달한다.
- `label`: dataset의 특정 `GameStep` row에 고유 action identity 라벨을 붙인다. `pick:card_1`, `pick_card:card_1`, `skip` 같은 짧은 별칭은 한 legal action으로 해석될 때만 허용한다.
- `train`: 라벨된 `GameStep`으로 PyTorch ranker를 학습한다.
- `recommend`: 저장된 `.pt` 모델과 현재 `GameStep`으로 후보별 추천 점수를 출력한다.
- `evaluate-model`: `--eval-dataset` holdout과 model을 받아 top-1/top-3, legal mask, value-head correlation, Brier score, score margin을 기록한다. 기존 `--dataset`은 deprecated 호환 alias로 warning을 낸다.
- `evaluate-play`: episode/play JSONL에서 win rate, floor/HP/step 평균, latency, timeout, misclick, illegal action, candidate recall을 기록한다. safety metric이 빠진 row는 기본 실패 지표로 계산하고, `--allow-missing-metrics`일 때 missing row count를 포함하며 missing candidate recall은 평균에서 제외한다.
- `act`: saved `GameStep`과 명시 action id로 dry-run/input event/native input action을 계획하거나 실행한다.
- `live-step`: 화면 capture 또는 fixture, OCR parsing, manual/model choice, input planning/execution을 한 번에 수행한다. post-input OCR fixture, fixture sequence, live frame polling 기반 acknowledgement/retry를 지원한다.
- `live-learn-loop`: 최초 시작 메뉴부터 gameplay, terminal, restart까지 `live-step` 경계를 반복한다. combat/card reward/relic choice/map/shop/event/rest 화면은 `--choice` 또는 `--allow-model-self-labels`일 때만 labeled `GameStep` JSONL에 누적하고, `--execute`에서는 transition ack `changed`일 때만 `GameStep`/`TrajectoryStep` append와 JSONL input log commit을 확정한다. terminal return을 같은 episode의 gameplay row에 전파하며, 지정 interval과 terminal 전파 직후 PyTorch 모델을 재학습/저장한다. `--region-calibration`은 반복 OCR parse에도 적용된다.
- `save-state backup`: 지정 save 파일을 backup directory로 복사한다.
- `save-state restore`: exact hashed backup save를 원 위치로 복원하고 기존 save는 pre-restore copy로 보존한다.
- `run-loop`: seed 목록, optional victory seed 목록, capture fixture/OCR로 seed episode JSONL을 생성한다.
- `evaluate-seeds`: seed episode JSONL에서 episode count, victory count, win rate, average steps를 요약하고, `--baseline`이 있으면 rule baseline 대비 delta를 출력한다.

## Data And Schema

- `GameStep`/`StructuredGameState`: player/card/relic/potion/monster/path/action/observation 상태를 entity-centric learning row로 round-trip한다.
- `EpisodeState`/`TrajectoryStep`: run/seed/game version/floor/room/turn transition과 state before/after, legal/selected action, reward, terminal, label source를 JSON/dict/JSONL로 round-trip한다.
- `PlayerState`: HP, max HP, block, energy, turn, strength/dexterity, vulnerable/weak/frail/artifact, poison/regen/intangible, character-specific resources를 보존한다.
- `CardInstance`: card id, zone, upgrade state, cost, type, rarity, temporary/generated/retain/exhaust/ethereal/innate flags를 보존한다.
- `RelicState`: acquisition order, counter, cooldown, combat/turn activation flags를 보존한다.
- `ActionCandidate`: 현재 가능한 행동 후보, legal flag/mask, source/target ids, path/shop/event ids, source `screen_box`, optional `target_screen_box`를 보존한다. identity는 action type과 entity field를 포함해 `play_card`/`discard_card`처럼 같은 카드 id를 쓰는 서로 다른 행동이 충돌하지 않게 한다.
- `ObservationQuality`: OCR confidence, field-level confidence, missing field, unknown token, catalog version을 저장해 Early Access catalog drift를 추적한다.
- `label_source`: 기존 row는 `human`으로 읽고, 기본 학습은 `human`/`search`/`heuristic`만 포함한다. `model_shadow`/`model_self`는 기본 학습에서 제외한다.
- `capture`/`capture-live`/`live-step`은 `--state-json`으로 플레이어, 카드, 유물, 포션, 몬스터, 경로 후보, 상점, 이벤트, 휴식 상태를 입력받고, 미제공 필드는 `missing_fields`에 기록한다.
- `RecognizedOption`/`ParsedScreen`: OCR에서 인식한 canonical option과 화면 resolution을 구조화한다.
- `live_state.extract_live_state`: OCR text에서 player HP/energy/block/turn/gold/floor, hand card, potion, monster HP/intent, map node, shop item, observed leave-shop option, event option, rest option을 typed state payload와 screen box로 추출한다. 중복 shop/event option label은 slot id로 분리한다.
- `actions.generate_legal_actions`: structured state에서 combat, card reward, map, shop, event, rest context의 state-derived legal action generator를 제공한다. Combat은 hand card, living monster target, usable potion, end turn을 entity-linked action으로 만들고, shop `leave_shop`은 관측된 leave option box가 있을 때만 생성한다.
- `AutomationAction`: action, option id, dry-run state, coordinate space, target box 또는 target sequence를 기반으로 click/keypress/sequence `input_plan`을 만든다.
- `WindowBounds`/`TargetWindow`: macOS target application/window identity와 bounds를 구조화해 relative option box를 screen absolute input plan으로 변환한다.
- 좌표 없는 `pick` action은 실행 계획 생성 시 실패한다. 좌표 없는 reward skip은 escape keypress, combat `end_turn`은 `e` keypress 계획을 사용한다.

## Screen Recognition

- synthetic/stable screenshot용 색상 기반 detector가 card reward, relic choice, skip button layout을 구분한다.
- OCR provider protocol을 통해 fixture OCR과 Tesseract TSV adapter를 같은 parsing 경로로 사용한다.
- 영어/한국어 alias catalog로 카드, 유물, skip text를 canonical id로 매핑한다.
- OCR로 시작 메뉴의 `Continue`/`계속`/`Single Player`, 모드 선택의 `Standard`, 캐릭터 선택의 `Ironclad`, terminal 화면의 `Victory!`/`Game Over`/`승리`/`게임 오버`와 `New Run`/`다시 시작` 재시작 버튼을 매핑한다.
- 카드 보상 OCR은 3개 카드와 skip button이 모두 인식될 때만 `card_reward`로 처리한다.
- 같은 catalog id가 여러 슬롯에 나오면 option id는 `strike_1`, `strike_2`처럼 slot-specific으로 분리하고, reward `CardInstance.card_id`는 canonical id인 `strike`로 유지한다.
- Tesseract TSV의 단어 row를 catalog-matched multi-word span으로 합쳐 `Burning Blood`, `Tiny House` 같은 인접 multi-word 항목을 별도 option으로 매칭한다.
- Terminal 판정은 confidence `0.60` 이상 token만 사용하고, Tesseract가 `Game`/`Over`처럼 terminal title을 단어 단위로 분리해도 adjacent phrase로 복원한다.
- reward layout은 resolution-independent 위치 조건으로 필터링한다.
- calibrated region JSON은 `reference_resolution`과 `card`/`relic`/`skip`/`menu` region boxes를 받아 현재 screenshot resolution으로 scale한다. `parse-screen`, `capture-live`, `live-step`, `live-learn-loop`의 OCR option filtering과 `detect_screen()`의 color component filtering에 적용된다.
- catalog-matched OCR token confidence가 `0.60` 미만이면 option으로 쓰지 않고 fail-closed 경로에 남긴다.
- combat/map/shop/event/rest required field가 missing이거나 `field_confidence < 0.60`이면 `PerceptionQualityError`로 fail-closed한다.
- 알 수 없는 layout이나 catalog에 없는 텍스트는 빈 학습 row로 저장하지 않고 실패하거나 무시한다.

## Machine Learning

- PyTorch `EntityTransformerActorCritic`은 global/player/card/relic/potion/monster/path/action/observation/decision-context token을 인코딩한다.
- 모델은 legal action mask를 policy logits에 적용하고, behavior cloning policy loss를 학습한다. value head loss는 실제 `StepOutcome`이 있는 row에서만 적용하며, explicit value target, discounted return, reward/floor/HP/terminal signal을 victory-only target보다 우선한다.
- 캐릭터별 모델 학습을 지원하며, 추천 시 `GameStep` character와 모델 character mismatch를 거부한다.
- `.pt` checkpoint로 모델 save/load를 수행하고, checkpoint load는 PyTorch safe `weights_only` 경로를 사용한다.
- 추천 결과는 best candidate와 candidates list를 JSON으로 출력한다.
- PPO, GNN map encoder, simulator-backed self-play는 확장 지점으로만 남아 있다.

## Automation And Input

- 모든 입력 실행은 기본 dry-run이다.
- `--execute`가 있을 때만 controller를 사용한다.
- 기본 backend는 `jsonl`이며, input event를 JSONL로 기록한다.
- `--input-backend native --execute`는 platform command로 실제 입력 계획을 전달한다.
- macOS native backend는 `osascript` System Events를 사용한다.
- `live-step --screenshot-out --target-process "Slay the Spire 2"`는 macOS `osascript` 또는 Windows PowerShell/user32 기반 detector로 정확히 하나의 matching process/window를 찾고, target-window crop을 window-relative action plan으로 처리한다.
- macOS native backend는 target process가 있으면 하나의 AppleScript 안에서 application activate, window identity/bounds 재조회, expected metadata 비교, click/key 실행을 순서대로 수행한다.
- Windows native backend는 target process가 있으면 하나의 PowerShell script 안에서 process/title/bounds 재조회, `SetForegroundWindow`, click/key 실행을 순서대로 수행한다.
- Linux native backend는 `xdotool`을 사용한다.
- Windows native backend는 PowerShell/user32 `SetCursorPos`/`mouse_event`로 click을 보내고, keypress는 기존 PowerShell SendKeys 경로를 유지한다.
- targeted combat card/potion action은 source box와 monster target box를 모두 가진 경우 source click 후 target click sequence로 실행한다. target id가 있는데 target screen box가 없으면 planning 단계에서 실패한다.
- combat `end_turn` action은 targetless skip/Escape가 아니라 `e` keypress로 계획한다.
- 테스트에서는 runner/monkeypatch를 주입해 실제 OS 입력을 보내지 않는다.
- Quartz/PyObjC PID-targeted input은 dependency 추가 없이 향후 확장 지점으로만 남겼다.

## Live Step

- `--capture-fixture`로 deterministic screenshot을 사용하거나, `--screenshot-out`으로 Pillow `ImageGrab.grab()` 결과를 저장한다.
- target window가 있으면 `--screenshot-out` capture는 Pillow `ImageGrab.grab(bbox=...)` 경로로 window bounds를 캡처한다.
- OCR parsing으로 현재 선택지를 만들고 `GameStep`을 구성한다.
- OCR state payload가 있으면 `step_factory`가 capture/state-json 값 위에 병합하고 legal action generator 결과에 screen box를 연결한다.
- `--choice`가 있으면 manual action id를 사용한다.
- `--model`이 있으면 저장된 추천 모델의 best action id를 사용한다.
- `--ack-ocr-fixture`가 있으면 입력 후 parsed frame과 이전 frame signature를 비교해 `changed`/`no_op`/`timeout` transition acknowledgement를 포함한다.
- `--ack-ocr-fixture-sequence --ack-max-retries N`은 fixture frame을 poll frame처럼 순서대로 소비하면서 no-op/timeout이면 action을 다시 보낸다. `N`은 0 이상의 정수여야 한다.
- `--ack-live-poll --ack-max-retries N`은 `--screenshot-out` 기반 live frame을 재캡처하고 같은 OCR parser로 acknowledgement를 계산한 뒤 retry한다. target window mode에서는 ack frame도 같은 bbox로 캡처한다.
- transition signature는 legal action identity를 정렬해 OCR 후보 순서만 바뀐 frame을 `no_op`으로 유지한다.
- 결과 JSON에는 `choice`, `action`, `input_plan`, `screenshot_path`가 포함되고, target process 사용 시 `target_window`가 포함된다.
- native backend는 `--execute` 없이 사용할 수 없다.

## Live Learn Loop

- `--capture-fixture`는 모든 iteration에서 같은 deterministic screenshot을 재사용한다.
- `--ocr-fixture-sequence`는 테스트/fixture 실행에서 iteration별 OCR frame을 순서대로 공급한다.
- fixture OCR JSON과 ack fixture sequence JSON은 Windows PowerShell 5.1의 BOM 포함 UTF-8 출력을 허용한다.
- `--screenshot-out live.png`는 `live-000001.png`, `live-000002.png`처럼 반복 안전한 파일명으로 캡처한다.
- 반복마다 OCR parsing 후 combat/card reward/relic choice/map gameplay 화면은 `--choice` 또는 `--model` 추천으로 action identity를 선택한다. `--choice` 라벨은 `chosen_action_id`가 채워진 `GameStep`으로 `--dataset` JSONL에 append한다.
- `--execute`로 gameplay label/model action을 보낼 때는 `--ack-ocr-fixture-sequence` 또는 `--ack-live-poll` transition acknowledgement가 필요하다. `changed`일 때만 dataset과 optional `--trajectory-out` append가 확정된다.
- ack 없음, `no_op`, `timeout`, controller error, fail-closed perception, dataset preflight failure는 `--failure-log` JSONL에 기록하고 dataset/trajectory append는 하지 않는다.
- 메뉴/모드/캐릭터/재시작 화면은 첫 legal action으로 입력 계획만 만들고 ML dataset에는 append하지 않는다.
- `--model`이 고른 gameplay action은 self-label 위험을 막기 위해 기본적으로 dataset에 append하지 않는다. 실험적으로 저장하려면 `--allow-model-self-labels`를 명시한다.
- terminal 화면은 `StepOutcome(terminal=True)`로 승패를 표시하고, `--episodes-out`이 있으면 episode, victory, floor, HP, labeled step count, restart action id를 JSONL로 기록한다. 같은 terminal frame이 반복되면 이미 reset된 episode를 steps=0 row로 다시 쓰지 않는다.
- 기본 동작은 dry-run이며 `--execute` 없이는 input controller를 만들지 않는다. `--input-backend native`는 `--execute` 없으면 실패한다.
- `--train-every N --model-out path.pt` 조합은 N개 신규 labeled row마다, 그리고 terminal return 전파 직후 `train_torch_model(load_game_steps(dataset), character, epochs, batch_size, device)` 후 `save_model`을 호출한다.
- `KeyboardInterrupt`는 traceback 없이 `steps`, `trained`, `interrupted`, `dataset`, `model` summary JSON을 출력하고 정상 종료한다.

## Runtime And Evaluation

- `capture_screen()`은 화면 캡처 실패를 OS screen recording permission/setup error로 감싸 보고한다.
- save backup/restore는 명시된 파일과 backup directory만 조작하며, save path hash를 포함한 exact backup 이름으로 같은 파일명 충돌과 old basename 오복원을 막는다.
- `score_branch_outcome()`은 victory/floor/HP/step weight로 terminal branch score를 계산한다.
- `mcts_seed_search()`는 UCT score로 branch path를 반복 sampling하고 가장 높은 observed rollout score를 반환한다.
- `search_save_state_branches()`는 score scorer와 bound scorer를 호출하기 전마다 backup save를 복원한다.
- seed loop는 현재 v1 boundary로, fixture/OCR 기반 episode row를 생성하고 실제 수행한 parsed choice 수를 `steps`, declared terminal result를 `victory`로 기록한다.
- seed evaluation은 victories, win rate, average steps를 계산한다.
- model/play evaluation은 정책 정확도, legal mask, calibration/value proxy, score margin, latency, transition timeout, misclick, illegal action, candidate recall을 계산한다.

## Docker And Packaging

- Dockerfile은 CLI 실행 이미지를 만든다.
- `scripts/build-windows-exe.ps1`은 Windows PowerShell에서 PyInstaller one-file console executable을 `dist/sts2-tas.exe`로 만든다.
- `.github/workflows/windows-exe.yml`은 Windows runner에서 exe smoke test 후 `sts2-tas-windows-x64` artifact를 업로드한다.
- `.dockerignore`는 local state와 generated output을 제외한다.
- README와 docker docs는 macOS/Linux/Windows 실행 경계를 설명한다.
- Python package entrypoint는 `sts2-tas = "sts2_tas.cli:main"`이다.

## Tests And Verification

- 현재 test suite는 schema, GameStep encoding/dataset/model, recognition, calibrated CV/OCR regions, live OCR, automation CLI, native input backend, live-step retry polling, branch scorer/MCTS, Docker asset을 검증한다.
- coverage gate는 `sts2_tas` 전체 100%를 요구한다.
- 최종 검증 명령:

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

## Safety Boundaries

- Steam/Godot process memory나 내부 runtime state는 읽지 않는다.
- 온라인/co-op/leaderboard 자동화는 구현하지 않았다.
- 실제 OS 입력은 `--execute`와 backend 명시가 필요하다.
- 실제 게임 창 end-to-end smoke와 OS permission provisioning은 자동 테스트에서 수행하지 않는다.
