# Architecture

## Data Flow

1. `sts2-tas capture` reads a screenshot and stores an unlabeled `DecisionSnapshot`.
2. `sts2-tas label` updates one JSONL row with `pick:<option_id>` or `skip`.
3. `sts2-tas train` converts labeled snapshots into per-option feature rows and trains a scikit-learn `DictVectorizer + DecisionTreeClassifier` recommender.
4. `sts2-tas recommend` loads a saved model and ranks the current snapshot options.

## DecisionSnapshot

Each snapshot stores:

- `game_version`, `branch`, `character`, `ascension`, `floor`
- `deck`, `relics`, `hp`, `gold`
- `options`, `chosen`, `skipped`, `screenshot_path`

Card decisions use `pick:<card_id>` or `skip`. Relic decisions use `pick:<relic_id>`.

## Screen Recognition

The v1 recognizer is intentionally narrow and deterministic. It detects synthetic or stable screenshots by color regions for:

- card reward options
- skip button
- relic choice options

Unknown layouts fail instead of creating empty-option training rows. This keeps the first ML pipeline testable before adding OCR, template matching, or a game-mod data bridge.

## Constraints

- Target UI assumption: English UI, fixed window size, single-player local run.
- StS2 Early Access changes must be handled by storing `game_version` and `branch` in every snapshot.
- Actual input execution is disabled in v1. A future `--execute` flag should require explicit user action and separate safety tests.
- Saved model files are loaded with `joblib`; only load trusted local model artifacts.
