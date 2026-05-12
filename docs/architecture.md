# Architecture

## Data Flow

1. `sts2-tas parse-screen` reads a screenshot and OCR tokens, then writes catalog-matched options.
2. `sts2-tas capture` or `capture-live` stores an unlabeled `DecisionSnapshot`.
3. `sts2-tas label` updates one JSONL row with `pick:<option_id>` or `skip`.
4. `sts2-tas train` converts labeled snapshots into per-option feature rows and trains a scikit-learn `DictVectorizer + DecisionTreeClassifier` recommender.
5. `sts2-tas recommend` loads a saved model and ranks the current snapshot options.
6. `sts2-tas act`, `run-loop`, and `evaluate-seeds` turn parsed options into dry-run input plans and seed-level episode summaries.

## DecisionSnapshot

Each snapshot stores:

- `game_version`, `branch`, `character`, `ascension`, `floor`
- `deck`, `relics`, `hp`, `gold`
- `options`, `chosen`, `skipped`, `screenshot_path`

Card decisions use `pick:<card_id>` or `skip`. Relic decisions use `pick:<relic_id>`.

## Screen Recognition

The recognizer keeps the original deterministic color path for synthetic fixtures and adds an OCR path for live screenshots. The OCR path is:

`layout detection -> OCR regions -> English/Korean catalog match -> canonical option id`

It currently recognizes:

- card reward options
- skip button
- relic choice options

Unknown layouts fail instead of creating empty-option training rows. OCR providers are pluggable: tests use a JSON/fake provider and live use can route through `--ocr-provider tesseract --ocr-language eng+kor`.

## Automation And Evaluation

`sts2-tas act` is dry-run by default and reports the planned `pick` or `skip` action as JSON. It writes an input event only with `--execute`.

`save-state backup` and `save-state restore` operate only on the explicit `--save` file and `--backup-dir`. Restore keeps a pre-restore copy before replacing the save file.

`run-loop` is a first live-loop boundary: it consumes seed lists, a capture fixture, OCR tokens, and a max step count, then records JSONL episodes. `evaluate-seeds` summarizes episode count, victories, win rate, and average steps.

## Constraints

- Target UI assumption: English/Korean UI, single-player local run, OCR-visible card/relic/skip text.
- StS2 Early Access changes must be handled by storing `game_version` and `branch` in every snapshot.
- Actual input execution requires `--execute`; default CLI behavior is dry-run.
- Steam/Godot process memory and internal runtime state are not read.
- Saved model files are loaded with `joblib`; only load trusted local model artifacts.
