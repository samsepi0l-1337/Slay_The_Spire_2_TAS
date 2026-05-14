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
- `live-learn-loop --model`의 self-label 저장을 기본 차단하고, 명시적 실험 플래그 `--allow-model-self-labels`만 허용했다.
- `act --target-process`는 `--coordinate-space window_relative`가 있을 때만 허용한다.
- Windows native target input은 process/title/bounds recheck, `SetForegroundWindow`, input 실행을 한 PowerShell script 안에 묶는다.
- OCR catalog match는 confidence `0.60` 미만 token을 action option으로 쓰지 않는다.
- source artifact hygiene를 위해 `.uv-cache/`, `build/`, `dist/`, `*.spec`을 ignore 대상에 추가했다.

## P0 Gaps

- Live state extractor: HP/max HP, block, energy, turn, gold, floor, hand/draw/discard/exhaust, relic counters, potion slots, monster HP/intents, map nodes를 화면에서 갱신해야 한다.
- Legal action integration: 현재 generator는 typed boundary이고 live OCR path는 아직 screen option 중심이다. `step_factory`가 state+screen evidence를 받아 combat/map/shop/event/rest/potion 후보를 만들도록 확장해야 한다.
- Transition acknowledgement: 입력 후 OCR/frame 상태 변화, debounce, retry, no-op, timeout을 분리해야 한다.
- Trajectory return: terminal outcome을 episode summary에만 두지 말고 gameplay rows에 Monte Carlo return 또는 TD target으로 전파해야 한다.

## P1 Gaps

- Versioned catalog: catalog를 외부 JSON으로 분리하고 Early Access patch drift를 기록해야 한다.
- Unknown OCR logging: unknown token, fuzzy match 후보, confidence threshold 통계를 field-level report로 남겨야 한다.
- Search/TAS loop: save-state backup/restore와 seed 고정으로 reward/map부터 branch-and-bound, 이후 combat shallow rollout/MCTS를 붙여야 한다.
- Numeric encoding: HP/gold/floor 등 numeric scale normalization과 observed/missing mask 결합이 필요하다.
- Windows DPI/hit-test: DPI scaling, clickable region margin, screenshot id, pre/post state hash, latency/error logging을 더해야 한다.

## Acceptance Targets

- state field accuracy >= 99%, unknown/missing field는 명시 기록.
- candidate recall >= 99%, illegal action execution 0건.
- target window race/move/focus 변경 시 fail-closed.
- model holdout top-1/top-3, calibration, value correlation이 rule baseline보다 우수.
- 동일 seed에서 floor/win rate/decision time이 rule baseline보다 개선.
- CI unit/integration tests, Windows exe smoke, source artifact hygiene 통과.
