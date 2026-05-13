# Architecture

## Data Flow

1. `sts2-tas parse-screen` reads a screenshot and OCR tokens, then writes catalog-matched options.
2. `sts2-tas capture` or `capture-live` stores an unlabeled `DecisionSnapshot`.
3. `sts2-tas label` updates one JSONL row with `pick:<option_id>` or `skip`.
4. `sts2-tas train --backend sklearn` converts labeled snapshots into per-option feature rows and trains a scikit-learn `DictVectorizer + DecisionTreeClassifier` baseline recommender.
5. `sts2-tas migrate-dataset` converts legacy `DecisionSnapshot` rows into reward-only `GameStep` rows for entity/action learning.
6. `sts2-tas train --backend torch` trains a PyTorch entity-centric actor-critic ranker over legal `ActionCandidate` tokens.
7. `sts2-tas recommend` loads a saved `.joblib` or `.pt` model and ranks the current snapshot options.
8. `sts2-tas live-step` captures a screenshot or uses `--capture-fixture`, parses OCR options, chooses from `--choice` or `--model`, and applies one dry-run/jsonl/native action.
9. `sts2-tas act`, `run-loop`, and `evaluate-seeds` turn parsed options into dry-run input plans and seed-level episode summaries.

## DecisionSnapshot

Each snapshot stores:

- `game_version`, `branch`, `character`, `ascension`, `floor`
- `deck`, `relics`, `hp`, `gold`
- `options`, `chosen`, `skipped`, `screenshot_path`

Card decisions use `pick:<card_id>` or `skip`. Relic decisions use `pick:<relic_id>`.

## GameStep Entity Ranker

`GameStep` is the v1 learning surface for the PyTorch backend. It stores a `StructuredGameState`, legal `ActionCandidate` list, optional `StepOutcome`, `ObservationQuality`, and the chosen action id. Legacy snapshots migrate to reward-only `GameStep` rows so existing captures remain usable.

The torch encoder tokenizes these groups:

- `GLOBAL`, `PLAYER`, `CARD`, `RELIC`, `POTION`
- `MONSTER`, `PATH`, `ACTION`, `OBSERVATION`, `DECISION_CONTEXT`

The `EntityTransformerActorCritic` scores only the current legal action candidates, masks illegal actions before policy selection, and predicts a value logit for later seed-loop outcome learning. It is behavior-cloning first; PPO, GNN map encoding, and simulator-backed self-play remain future work.

## Screen Recognition

The recognizer keeps the original deterministic color path for synthetic fixtures and adds an OCR path for live screenshots. `live-step --screenshot-out` uses Pillow `ImageGrab.grab()` through a small injectable runtime wrapper; tests inject a fake grabber and never capture the real desktop. The OCR path is:

`layout detection -> OCR regions -> English/Korean catalog match -> canonical option id`

It currently recognizes:

- card reward options
- skip button
- relic choice options

Card rewards require all three card options plus the skip button before the parser returns a `card_reward`; partial OCR fails closed instead of producing an incomplete decision surface. Duplicate catalog ids are made slot-specific, for example `strike_1`, `strike_2`, and `strike_3`, so repeated card names remain selectable. Tesseract TSV word rows are combined only into catalog-matched multi-word spans, so adjacent options such as `Burning Blood` and `Tiny House` stay separate instead of becoming one full-line token.

Unknown layouts fail instead of creating empty-option training rows. OCR providers are pluggable: tests use a JSON/fake provider and live use can route through `--ocr-provider tesseract --ocr-language eng+kor`.

## Automation And Evaluation

`sts2-tas act` is dry-run by default and reports the planned `pick` or `skip` action as JSON, including the target box and click/key input plan when available. It writes an input event only with `--execute` and the default `--input-backend jsonl`.

`sts2-tas live-step` emits JSON with `choice`, `action`, `input_plan`, and `screenshot_path`. `--capture-fixture` keeps tests and fixture runs deterministic; `--screenshot-out` writes the live captured screen before OCR. Live capture failures are reported as permission/setup errors and should be retried only after OS screen-recording permission is granted.

`live-step --screenshot-out --target-process "Slay the Spire 2"` captures the target window bbox and marks the resulting snapshot as `coordinate_space: "window_relative"` with `target_window` metadata. `act --target-process` only translates coordinates for snapshots whose window-relative metadata matches the current detected target window. Legacy snapshots without coordinate metadata default to `screen_absolute` and fail closed instead of adding the window offset a second time.

`--input-backend native --execute` sends the same plan through a platform adapter instead of writing JSONL. macOS uses `osascript` System Events, Linux uses `xdotool`, and Windows currently supports only the keypress path through PowerShell SendKeys while click input fails explicitly. With a target window, macOS builds one AppleScript that activates the application, re-reads the window title/bounds inside the same script, errors if the expected metadata changed, then sends click/key input. Tests inject subprocess/window runners so no real OS input is sent.

Production real-input usage combines target-window detection, native input, and the explicit execution gate: `live-step --screenshot-out ... --target-process "Slay the Spire 2" --input-backend native --execute`. Replaying a saved window-relative snapshot uses the same gate with `act --snapshot ... --target-process "Slay the Spire 2" --input-backend native --execute`. Omit `--input-backend native --execute` first to verify the dry-run plan and target metadata.

Quartz/PyObjC targeted PID event delivery is intentionally only an extension point for now. No dependency is added in this boundary.

`save-state backup` and `save-state restore` operate only on the explicit `--save` file and `--backup-dir`. Backup names include a stable hash of the save path so saves with the same file name in different directories do not overwrite each other. Restore requires that exact hashed backup and keeps a pre-restore copy before replacing the save file.

`run-loop` is a first live-loop boundary: it consumes seed lists, optional `--victory-seeds`, a capture fixture, OCR tokens, and a max step count, then records JSONL episodes. In this fixture-only boundary it performs one parsed choice per seed, records the actual executed step count instead of pretending all `--max-steps` were consumed, and stores declared victory outcomes per seed. `evaluate-seeds` summarizes episode count, victories, win rate, and average steps.

## Constraints

- Target UI assumption: English/Korean UI, single-player local run, OCR-visible card/relic/skip text.
- StS2 Early Access changes must be handled by storing `game_version` and `branch` in every snapshot.
- Actual input execution requires `--execute`; default CLI behavior is dry-run and `native` is rejected unless `--execute` is present.
- Steam/Godot process memory and internal runtime state are not read.
- Saved model files are loaded with `joblib` or PyTorch checkpoints; only load trusted local model artifacts.
