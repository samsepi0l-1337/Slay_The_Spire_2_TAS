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
- Tesseract split token의 `Game`/`Over`, 한국어 `승리`/`게임 오버` terminal alias를 confidence `0.60` 이상일 때만 episode boundary로 처리한다.
- `live-learn-loop`가 combat/map도 gameplay로 취급해 manual/model choice, dataset append, training path를 동일하게 탄다.
- terminal return 전파 직후 모델을 재학습하고, 반복 terminal frame은 steps=0 episode summary로 중복 기록하지 않는다.
- combat `end_turn`은 targetless skip/Escape가 아니라 `e` keypress로 실행 계획을 만든다.
- transition signature는 legal action identity를 정렬해 OCR ordering 변화만으로 retry가 suppress되지 않게 한다.
- save-state branch search는 bound scorer 평가 전에도 save를 복원한다.
- live OCR overlay가 `cards` 같은 entity payload를 제공하면 `cards.metadata` 같은 stale nested missing field를 제거한다.
- `--ack-max-retries` 음수 입력을 실행 전 명시적으로 거부한다.
- `EpisodeState`/`TrajectoryStep` JSONL을 추가해 run id, seed, game version, floor, room type, turn index, state before/after, legal/selected action, reward, terminal, label source를 transition row로 저장한다.
- `label_source`를 `human`, `heuristic`, `search`, `model_shadow`, `model_self`로 분리하고 기존 `GameStep` row는 `human`으로 역직렬화한다.
- 기본 학습은 `human`/`search`와 heuristic row만 사용하고 `model_shadow`/`model_self` row를 제외한다.
- value target은 explicit `value_target`, `discounted_return`, reward/floor/HP/terminal signal을 우선하고, richer signal이 없을 때만 victory boolean으로 fallback한다.
- `evaluate-model`과 `evaluate-play`를 추가해 model holdout/top-k/legal mask/calibration/value proxy와 play latency/timeout/misclick/illegal action/candidate recall을 리포트한다.
- `ObservationQuality.field_confidence`와 context별 required field gate를 추가해 combat/map/shop/event/rest 인식이 missing 또는 confidence `<0.60`이면 fail-closed한다.
- shop/event/rest typed option state, legal action generator, OCR fixture grammar, screen box binding을 추가했다.
- `live-learn-loop --execute`는 gameplay label/model action에서 transition ack `changed`일 때만 `GameStep`/`TrajectoryStep`을 append하고, ack 없음/no-op/timeout/controller error/perception failure/preflight failure는 failure log만 기록한다.
- `evaluate-model`은 `--eval-dataset`과 value-head sigmoid score 기반 `value_correlation`을 사용한다.
- `evaluate-play`는 safety metric이 빠진 row를 기본 실패 지표로 계산하고, `--allow-missing-metrics`에서만 missing row count를 리포트한다.

## P0 Gaps

- Live state extractor: OCR text grammar 기반 HP/max HP, block, energy, turn, gold, floor, hand, potion, monster, map, shop/event/rest option 추출과 calibrated CV/OCR region filtering은 시작됐다. draw/discard/exhaust, relic counters, per-entity status detail은 남아 있다.
- Legal action integration: combat/card_reward/relic_choice/map/shop/event/rest는 live state와 generator가 연결됐다. non-monster targeting과 복합 이벤트/상점 제약은 남아 있다.
- Transition acknowledgement: changed/no-op/timeout 분리, fixture sequence retry, live frame polling retry, action-order stable signature, execute+changed-only append는 구현됐다. debounce, retry backoff policy, real animation latency tuning은 남아 있다.
- Trajectory return: terminal outcome을 gameplay rows에 Monte Carlo return으로 전파하고 terminal 직후 재학습한다. `TrajectoryStep` JSONL, reward/return-aware value target, changed-only trajectory append는 구현됐다. TD target과 richer per-step reward shaping은 남아 있다.

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
