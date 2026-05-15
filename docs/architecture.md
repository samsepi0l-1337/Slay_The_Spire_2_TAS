# Architecture

## Data Flow

1. `sts2-tas parse-screen` reads a screenshot and OCR tokens, optionally filters them through a calibrated region map, then writes catalog-matched options plus live state evidence when the OCR text carries player/hand/monster/map fields.
2. `sts2-tas capture` or `capture-live` stores an unlabeled `GameStep` row.
3. `sts2-tas label` updates one `GameStep` JSONL row with an `ActionCandidate.identity`, for example `pick_card|option=card_1` or `skip_reward|option=skip`. CLI choices still accept short aliases such as `pick:card_1`, `pick_card:card_1`, and `skip` when they resolve to one legal action.
4. `sts2-tas train` trains a PyTorch entity-centric actor-critic ranker over legal `ActionCandidate` tokens.
5. `sts2-tas recommend` loads a saved `.pt` checkpoint and ranks the current `GameStep` actions.
6. `sts2-tas evaluate-model --eval-dataset` measures recommendation accuracy, legal-action masking, calibration, value-head correlation, and score margins over labeled holdout rows.
7. `sts2-tas live-step` captures a screenshot or uses `--capture-fixture`, parses OCR options/state, chooses from `--choice` or `--model`, applies dry-run/jsonl/native input, and can poll post-input frames for retryable transition acknowledgement.
8. `sts2-tas live-learn-loop` repeats the live-step boundary across start menus, gameplay decisions, terminal screens, and restarts. It appends labeled `GameStep`/`TrajectoryStep` rows only for supervised combat/card/relic/map/shop/event/rest gameplay decisions, and only after transition ack reports `changed` when `--execute` is used. It propagates terminal returns to the current episode's gameplay rows and can retrain/save a Torch model every N new labels or immediately after terminal return propagation.
9. `sts2-tas act`, `run-loop`, `evaluate-seeds`, `evaluate-play`, and branch search helpers turn parsed actions into dry-run input plans, seed-level episode summaries, baseline comparisons, play quality metrics, branch outcome scores, branch-and-bound candidates, and MCTS candidates.

## GameStep Entity Ranker

`GameStep` is the learning and recommendation surface. It stores a `StructuredGameState`, legal `ActionCandidate` list, optional `StepOutcome`, `ObservationQuality`, the chosen action id, and `label_source`. Existing rows without `label_source` load as `human`.

The torch encoder tokenizes these groups:

- `GLOBAL`, `PLAYER`, `CARD`, `RELIC`, `POTION`
- `MONSTER`, `PATH`, `ACTION`, `OBSERVATION`, `DECISION_CONTEXT`

The `EntityTransformerActorCritic` scores only the current legal action candidates, masks illegal actions before policy selection, and predicts a value logit for later seed-loop outcome learning. Default training uses supervised `human`, `search`, and `heuristic` labels; `model_shadow` and `model_self` rows are excluded. Value targets prefer explicit `StepOutcome.value_target`, then `discounted_return`, then reward/floor/HP/terminal shaping, and only fall back to victory when no richer signal exists. It is behavior-cloning first; PPO, GNN map encoding, and simulator-backed self-play remain future work.

## Trajectory Schema

`EpisodeState` records run id, seed, game version, floor, room type, and turn index for one point in an episode. `TrajectoryStep` records the transition-level row: run id, seed, game version, floor, room type, turn index, state before, legal actions, selected action, state after, reward, terminal, and label source. The schema round-trips through dict/JSON and supports JSONL load/write for trajectory-level evaluation.

## Game State Coverage

The schema includes the gameplay fields needed for StS2-style decisions:

- player HP, max HP, block, energy, turn, strength, dexterity, vulnerable, weak, frail, artifact, poison, regen, intangible, gold, and character-specific resources
- card instances with zone, upgrade state, cost, type, rarity, generated/temporary/retain/exhaust/ethereal/innate flags
- relic state with acquisition order, counter, cooldown, and activation flags
- potion, monster, path, observation, and decision-context entities
- action candidates with legal mask, source/target ids, path/shop/event/rest ids, and optional screen box for input planning

`capture`, `capture-live`, and `live-step` accept direct player-state flags plus `--state-json`. The JSON path is the preferred route for real learning rows because it can carry hand/deck zones, current costs, relic counters, potion slots, monster intents, path candidates, shop items, event options, and rest options in one typed payload. Any value that the capture path cannot observe or that the caller does not provide is preserved in `ObservationQuality.missing_fields` instead of being silently treated as known. OCR-derived `field_confidence` is stored per required field, and combat/map/shop/event/rest parsed screens fail closed when required fields are missing or below `0.60`. OCR card rewards are also added as `CardInstance` rows with `zone="reward"` so the model can score the candidate card as an entity token, not only as an action id.

`sts2_tas.live_state.extract_live_state()` consumes OCR text such as `HP 65/80`, `Energy 3/3`, `Hand Strike cost 1 attack`, `Monster Jaw Worm 30/44 block 3 attack 7x1`, and `Path node-a elite ...`, then returns typed state payload, screen boxes, missing fields, and unknown tokens. `sts2_tas.cv_calibration.RegionCalibration` adds calibrated CV/OCR region filtering for card/relic/skip/menu regions before options are accepted.

`sts2_tas.actions.generate_legal_actions()` is the state-derived legal action generator boundary. It emits typed candidates for combat cards, targeted potions, end turn, card rewards, and map path choices. `step_factory` feeds parsed live state into this generator and attaches source plus target screen boxes from OCR evidence. Targeted combat/potion actions become two-click sequences; if the monster target box is missing, input planning fails closed instead of clicking only the source. Combat `end_turn` is a targetless `e` keypress instead of Escape/menu input. Unsupported contexts still return no candidates instead of inventing actions.

## Screen Recognition

The recognizer keeps the deterministic color path for synthetic fixtures and adds an OCR path for live screenshots. `live-step --screenshot-out` uses Pillow `ImageGrab.grab()` through an injectable runtime wrapper; tests inject a fake grabber and never capture the real desktop. The OCR path is:

`layout detection -> OCR regions -> English/Korean catalog match -> canonical option id`

It currently recognizes:

- start menu single-player selection
- mode selection
- character selection
- card reward options
- skip button
- relic choice options
- victory/game over terminal screens with a new-run restart action
- OCR-state-only combat/map screens when typed live state text is present

Card rewards require all three card options plus the skip button before the parser returns a `card_reward`; partial OCR fails closed instead of producing an incomplete decision surface. Duplicate catalog ids are made slot-specific for option ids, for example `strike_1`, `strike_2`, and `strike_3`, so repeated card names remain selectable while reward `CardInstance.card_id` stays canonical as `strike`.

Unknown layouts fail instead of creating empty-option training rows. OCR providers are pluggable: tests use a JSON/fake provider and live use can route through `--ocr-provider tesseract --ocr-language eng+kor`. `--region-calibration regions.json` accepts `reference_resolution` and named `regions` so the same configured regions scale to the current screenshot resolution. Catalog-matched OCR tokens below confidence `0.60` are ignored, so partial or low-confidence reward layouts fail closed. Terminal detection uses the same confidence floor and rebuilds adjacent OCR words such as `Game`/`Over`; Korean `승리` and `게임 오버` are accepted when paired with a restart button.

## Automation And Evaluation

`sts2-tas act` is dry-run by default and reads a saved `GameStep`. It reports the planned `pick` or `skip` action as JSON, including the target box and click/key input plan when available. It writes an input event only with `--execute` and the default `--input-backend jsonl`. `act --target-process` is accepted only with `--coordinate-space window_relative`; saved screen-absolute steps must stay target-free to avoid stale coordinate translation.

`sts2-tas live-step` emits JSON with `choice`, `action`, `input_plan`, and `screenshot_path`. `--capture-fixture` keeps tests and fixture runs deterministic; `--screenshot-out` writes the live captured screen before OCR. `--ack-ocr-fixture` parses one post-input OCR frame. `--ack-ocr-fixture-sequence --ack-max-retries N` and `--ack-live-poll --ack-max-retries N` apply the action once, poll a frame, classify `changed`/`no_op`/`timeout`, and retry acknowledgement by polling another post-input frame while the acknowledgement says retry is recommended. They do not resend the same input during ack retry. `N` must be non-negative, and transition signatures sort legal action identities so OCR ordering jitter does not look like a state change.

`sts2-tas live-learn-loop` reuses the same capture/OCR/action planning contract in a bounded or user-interrupted loop. `--max-steps` makes the loop testable, `--capture-fixture` reuses the same fixture, and live screenshot capture writes numbered filenames derived from `--screenshot-out` so repeated runs do not overwrite one another. It appends selected combat/card/relic/map/shop/event/rest gameplay actions as `chosen_action_id` in `--dataset` only when the label is supervised by `--choice` or the explicit `--allow-model-self-labels` experiment flag. With `--execute`, gameplay labels require `--ack-ocr-fixture-sequence` or `--ack-live-poll`; otherwise no input is sent, the row is logged as `missing_transition_ack` when `--failure-log` is provided, and it is not persisted. `changed` is the only ack status that commits `GameStep`, optional `--trajectory-out` rows, and JSONL input logs. `no_op`, `timeout`, controller errors, perception quality failures, and dataset preflight failures append only to `--failure-log` when provided. Menu, mode, character, and restart actions are planned but not persisted as ML labels. Optional `--train-every N --model-out model.pt` retrains from the full dataset after every N newly appended labels.

The production live-learning target is a Windows local interactive session with the game window visible. SSH from macOS is not the runtime substrate for capture and native input; it is only a maintenance path for syncing files, launching an interactive scheduled task, and collecting logs. Docker is likewise limited to CLI/model execution and fixture or host-provided screenshot processing. Any diagnosis of live ML data collection starts from the Windows local session, target process metadata, OCR availability, and transition ack evidence.

Terminal screens produce a `StepOutcome` with `terminal=True`. The loop writes the terminal victory/loss return back onto the current episode's labeled gameplay rows as non-terminal `StepOutcome` values, retrains once after that propagation when training output is configured, then writes one episode JSON row with victory status, reached floor, remaining HP, labeled gameplay step count since the previous terminal, and the restart action id. Repeated terminal frames after the episode reset are ignored for summary output instead of writing steps=0 duplicates. It then plans the restart/new-run input action and continues the same loop so learning can resume on the next run.

`live-step --screenshot-out --target-process "Slay the Spire 2"` captures the target window bbox, parses the cropped screenshot, treats option boxes as `window_relative`, and passes the current target window directly into the input plan. On Windows, borderless/no-title games should use the process name, for example `--target-process SlayTheSpire2`; detection and input guard enumerate top-level visible windows by process id instead of relying on `MainWindowHandle`. Saved `GameStep` rows are screen-absolute for `act` unless the caller explicitly uses `--coordinate-space window_relative`; target-window translation is normally kept inside the live-step capture/act cycle to avoid stale window metadata.

`--input-backend native --execute` sends the same plan through a platform adapter instead of writing JSONL. macOS uses `osascript` System Events, Linux uses `xdotool`, and Windows uses PowerShell with `user32` for target-window detection and click input while keeping SendKeys for keypresses. With a target window, the controller re-detects the process/window metadata before each input and fails closed if it changed; macOS keeps activate/check/click in one AppleScript, and Windows keeps process/title/bounds recheck, `SetForegroundWindow`, and click/keypress in one PowerShell script. Empty Windows titles are valid when the bounds and owning process still match. Tests inject subprocess/window runners so no real OS input is sent.

`AutomationAction.input_plan()` remains single-click/key by default. When a candidate carries both `screen_box` and `target_screen_box`, it returns `{"kind": "sequence", "steps": [...]}` and native backends send source and target clicks in order.

Production real-input usage combines target-window detection, native input, and the explicit execution gate:

```bash
live-step --screenshot-out ... --target-process "Slay the Spire 2" --input-backend native --execute
```

Omit `--input-backend native --execute` first to verify the dry-run plan and target metadata.

Quartz/PyObjC targeted PID event delivery is intentionally only an extension point for now. No dependency is added in this boundary.

`save-state backup` and `save-state restore` operate only on the explicit `--save` file and `--backup-dir`. Backup names include a stable hash of the save path so saves with the same file name in different directories do not overwrite each other. `runtime.search_save_state_branches()` wraps this restore boundary around `branch_and_bound_seed()` so each score and bound scorer sees the same save-state baseline before evaluating a candidate path. `runtime.score_branch_outcome()` scores terminal progress using victory/floor/HP/step weights, and `runtime.mcts_seed_search()` performs UCT-style repeated branch sampling with the same scorer callback contract.

`run-loop` consumes seed lists, optional `--victory-seeds`, a capture fixture, OCR tokens, and a max step count, then records JSONL episodes. In this fixture-only boundary it performs one parsed choice per seed, records the actual executed step count, and stores declared victory outcomes per seed. `evaluate-seeds` summarizes episode count, victories, win rate, and average steps; with `--baseline`, it also emits candidate-vs-rule-baseline deltas. `evaluate-play` summarizes play JSONL with win rate, average floor/HP/steps, latency, transition timeout rate, misclick rate, illegal action rate, and candidate recall. Missing safety metrics are scored as failures by default; `--allow-missing-metrics` adds missing-row counts for legacy or partial logs and excludes missing candidate recall from its mean.

## Constraints

- Target UI assumption: English/Korean UI, single-player local run, OCR-visible card/relic/skip text.
- StS2 Early Access changes must be handled by storing `game_version`, `branch`, and `catalog_version` in every learning row.
- Actual input execution requires `--execute`; default CLI behavior is dry-run and `native` is rejected unless `--execute` is present.
- Steam/Godot process memory and internal runtime state are not read.
- Saved model files are loaded as `.pt` PyTorch checkpoints with safe tensor-only loading; only load trusted local model artifacts.
