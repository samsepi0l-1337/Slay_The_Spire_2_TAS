# V1 Gaps

검토 기준: `StS2_TAS_critical_improvement_plan_KR.docx`, 2026-05-14.

현재 구현은 안전한 화면 인식/입력 MVP다. 상시 실행 TAS로 보려면 아래 루프를 닫아야 한다.

```text
Window capture
-> OCR/CV perception
-> structured state with confidence/missing masks
-> legal action generator
-> rule/model/search decision
-> target-guarded input
-> transition acknowledgement
-> trajectory/reward feedback
```

## Implemented In This Update

- `actions.generate_legal_actions()`를 추가해 combat/card_reward/map의 state-derived legal action generator 경계를 만들었다.
- `live_state.extract_live_state()`를 추가해 OCR text에서 HP/max HP, block, energy, turn, gold, floor, hand card, potion, monster HP/intent, map node를 typed payload와 screen box로 추출한다.
- `step_factory`가 parsed OCR state+screen evidence를 병합하고 `generate_legal_actions()` 결과에 screen box를 붙여 combat/card_reward/map live path에서 같은 후보 표면을 사용한다.
- `transition.acknowledge_transition()`과 `live-step --ack-ocr-fixture`를 추가해 입력 후 changed/no-op/timeout과 retry 권고를 분리하는 검증 경계를 만들었다.
- `live-learn-loop` terminal outcome을 같은 episode의 gameplay `GameStep` row에 Monte Carlo return 형태의 `StepOutcome`으로 전파한다.
- `runtime.branch_and_bound_seed()`와 `search_save_state_branches()`를 추가해 save backup/restore 기반 branch 평가 시작점을 만들었다.
- `evaluate-seeds --baseline`을 추가해 candidate episode와 rule baseline episode의 win rate/average steps/victory delta를 리포트한다.
- `live-learn-loop --model`의 self-label 저장을 기본 차단하고, 명시적 실험 플래그 `--allow-model-self-labels`만 허용했다.
- `act --target-process`는 `--coordinate-space window_relative`가 있을 때만 허용한다.
- Windows native target input은 process/title/bounds recheck, `SetForegroundWindow`, input 실행을 한 PowerShell script 안에 묶는다.
- OCR catalog match는 confidence `0.60` 미만 token을 action option으로 쓰지 않는다.
- source artifact hygiene를 위해 `.uv-cache/`, `build/`, `dist/`, `*.spec`을 ignore 대상에 추가했다.
- `cv_calibration.RegionCalibration`과 `--region-calibration`을 추가해 OCR option filtering과 color component detection이 calibrated card/relic/skip/menu regions를 사용한다.
- targeted combat card/potion action에 `target_screen_box`를 연결하고 source+monster multi-click sequence를 `AutomationAction`/jsonl/native backend까지 전달한다.
- `live-step --ack-ocr-fixture-sequence`와 `--ack-live-poll`에 `--ack-max-retries`를 연결해 no-op/timeout acknowledgement에서 실제 retry input을 수행한다.
- `score_branch_outcome()`과 `mcts_seed_search()`를 추가해 branch outcome scorer와 UCT-style MCTS candidate search를 제공한다.

## P0 Gaps

- Live state extractor: OCR text grammar 기반 HP/max HP, block, energy, turn, gold, floor, hand, potion, monster, map 추출과 calibrated CV/OCR region filtering은 시작됐다. draw/discard/exhaust, relic counters, field-level confidence는 남아 있다.
- Legal action integration: combat/card_reward/map은 live OCR state와 generator가 연결됐다. targeted combat/potion multi-click은 구현됐다. shop/event/rest와 non-monster targeting은 남아 있다.
- Transition acknowledgement: changed/no-op/timeout 분리, fixture sequence retry, live frame polling retry는 구현됐다. debounce, latency/error metrics, retry backoff policy는 남아 있다.
- Trajectory return: terminal outcome을 gameplay rows에 Monte Carlo return으로 전파한다. TD target, discounted return, per-step reward shaping은 남아 있다.

## P1 Gaps

- Versioned catalog: catalog를 외부 JSON으로 분리하고 Early Access patch drift를 기록해야 한다.
- Unknown OCR logging: unknown token, fuzzy match 후보, confidence threshold 통계를 field-level report로 남겨야 한다.
- Search/TAS loop: save-state restore 기반 branch-and-bound, outcome scorer, MCTS 함수는 생겼다. CLI orchestration, real save-state rollout driver, richer reward/map scorer는 남아 있다.
- Numeric encoding: HP/gold/floor 등 numeric scale normalization과 observed/missing mask 결합이 필요하다.
- Windows DPI/hit-test: DPI scaling, clickable region margin, screenshot id, pre/post state hash, latency/error logging을 더해야 한다.

## Acceptance Targets

- state field accuracy >= 99%, unknown/missing field는 명시 기록.
- candidate recall >= 99%, illegal action execution 0건.
- target window race/move/focus 변경 시 fail-closed.
- model holdout top-1/top-3, calibration, value correlation이 rule baseline보다 우수.
- 동일 seed에서 floor/win rate/decision time이 rule baseline보다 개선.
- CI unit/integration tests, Windows exe smoke, source artifact hygiene 통과.
