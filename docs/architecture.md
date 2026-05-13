# Architecture

## Data Flow

1. `sts2-tas parse-screen` reads a screenshot and OCR tokens, then writes catalog-matched options.
2. `sts2-tas capture` or `capture-live` stores an unlabeled `GameStep` row.
3. `sts2-tas label` updates one `GameStep` JSONL row with an `ActionCandidate.identity`, for example `pick_card|option=card_1` or `skip_reward|option=skip`. CLI choices still accept short aliases such as `pick:card_1`, `pick_card:card_1`, and `skip` when they resolve to one legal action.
4. `sts2-tas train` trains a PyTorch entity-centric actor-critic ranker over legal `ActionCandidate` tokens.
5. `sts2-tas recommend` loads a saved `.pt` checkpoint and ranks the current `GameStep` actions.
6. `sts2-tas live-step` captures a screenshot or uses `--capture-fixture`, parses OCR options, chooses from `--choice` or `--model`, and applies one dry-run/jsonl/native action.
7. `sts2-tas act`, `run-loop`, and `evaluate-seeds` turn parsed actions into dry-run input plans and seed-level episode summaries.

## GameStep Entity Ranker

`GameStep` is the learning and recommendation surface. It stores a `StructuredGameState`, legal `ActionCandidate` list, optional `StepOutcome`, `ObservationQuality`, and the chosen action id.

The torch encoder tokenizes these groups:

- `GLOBAL`, `PLAYER`, `CARD`, `RELIC`, `POTION`
- `MONSTER`, `PATH`, `ACTION`, `OBSERVATION`, `DECISION_CONTEXT`

The `EntityTransformerActorCritic` scores only the current legal action candidates, masks illegal actions before policy selection, and predicts a value logit for later seed-loop outcome learning. Value loss is applied only to rows with a real `StepOutcome`, so unlabeled outcome rows do not train as false losses. It is behavior-cloning first; PPO, GNN map encoding, and simulator-backed self-play remain future work.

## Game State Coverage

The schema includes the gameplay fields needed for StS2-style decisions:

- player HP, max HP, block, energy, turn, strength, dexterity, vulnerable, weak, frail, artifact, poison, regen, intangible, gold, and character-specific resources
- card instances with zone, upgrade state, cost, type, rarity, generated/temporary/retain/exhaust/ethereal/innate flags
- relic state with acquisition order, counter, cooldown, and activation flags
- potion, monster, path, observation, and decision-context entities
- action candidates with legal mask, source/target ids, path/shop/event ids, and optional screen box for input planning

`capture`, `capture-live`, and `live-step` accept direct player-state flags plus `--state-json`. The JSON path is the preferred route for real learning rows because it can carry hand/deck zones, current costs, relic counters, potion slots, monster intents, and path candidates in one typed payload. Any value that the capture path cannot observe or that the caller does not provide is preserved in `ObservationQuality.missing_fields` instead of being silently treated as known. OCR card rewards are also added as `CardInstance` rows with `zone="reward"` so the model can score the candidate card as an entity token, not only as an action id.

## Screen Recognition

The recognizer keeps the deterministic color path for synthetic fixtures and adds an OCR path for live screenshots. `live-step --screenshot-out` uses Pillow `ImageGrab.grab()` through an injectable runtime wrapper; tests inject a fake grabber and never capture the real desktop. The OCR path is:

`layout detection -> OCR regions -> English/Korean catalog match -> canonical option id`

It currently recognizes:

- card reward options
- skip button
- relic choice options

Card rewards require all three card options plus the skip button before the parser returns a `card_reward`; partial OCR fails closed instead of producing an incomplete decision surface. Duplicate catalog ids are made slot-specific for option ids, for example `strike_1`, `strike_2`, and `strike_3`, so repeated card names remain selectable while reward `CardInstance.card_id` stays canonical as `strike`.

Unknown layouts fail instead of creating empty-option training rows. OCR providers are pluggable: tests use a JSON/fake provider and live use can route through `--ocr-provider tesseract --ocr-language eng+kor`.

## Automation And Evaluation

`sts2-tas act` is dry-run by default and reads a saved `GameStep`. It reports the planned `pick` or `skip` action as JSON, including the target box and click/key input plan when available. It writes an input event only with `--execute` and the default `--input-backend jsonl`.

`sts2-tas live-step` emits JSON with `choice`, `action`, `input_plan`, and `screenshot_path`. `--capture-fixture` keeps tests and fixture runs deterministic; `--screenshot-out` writes the live captured screen before OCR.

`live-step --screenshot-out --target-process "Slay the Spire 2"` captures the target window bbox, parses the cropped screenshot, treats option boxes as `window_relative`, and passes the current target window directly into the input plan. Saved `GameStep` rows are screen-absolute for `act`; target-window translation is kept inside the live-step capture/act cycle to avoid stale window metadata.

`--input-backend native --execute` sends the same plan through a platform adapter instead of writing JSONL. macOS uses `osascript` System Events, Linux uses `xdotool`, and Windows currently supports only the keypress path through PowerShell SendKeys while click input fails explicitly. With a target window, macOS builds one AppleScript that activates the application, re-reads the window title/bounds inside the same script, errors if the expected metadata changed, then sends click/key input. Tests inject subprocess/window runners so no real OS input is sent.

Production real-input usage combines target-window detection, native input, and the explicit execution gate:

```bash
live-step --screenshot-out ... --target-process "Slay the Spire 2" --input-backend native --execute
```

Omit `--input-backend native --execute` first to verify the dry-run plan and target metadata.

Quartz/PyObjC targeted PID event delivery is intentionally only an extension point for now. No dependency is added in this boundary.

`save-state backup` and `save-state restore` operate only on the explicit `--save` file and `--backup-dir`. Backup names include a stable hash of the save path so saves with the same file name in different directories do not overwrite each other.

`run-loop` consumes seed lists, optional `--victory-seeds`, a capture fixture, OCR tokens, and a max step count, then records JSONL episodes. In this fixture-only boundary it performs one parsed choice per seed, records the actual executed step count, and stores declared victory outcomes per seed. `evaluate-seeds` summarizes episode count, victories, win rate, and average steps.

## Constraints

- Target UI assumption: English/Korean UI, single-player local run, OCR-visible card/relic/skip text.
- StS2 Early Access changes must be handled by storing `game_version`, `branch`, and `catalog_version` in every learning row.
- Actual input execution requires `--execute`; default CLI behavior is dry-run and `native` is rejected unless `--execute` is present.
- Steam/Godot process memory and internal runtime state are not read.
- Saved model files are loaded as `.pt` PyTorch checkpoints with safe tensor-only loading; only load trusted local model artifacts.
