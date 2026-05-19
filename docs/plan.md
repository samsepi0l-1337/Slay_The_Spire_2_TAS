# Rewrite Plan

This document records the full architecture rewrite target and the current fixture-based implementation boundary.

Related documents:

- `docs/architecture.md`: target runtime contract.
- `docs/implemented-work.md`: current ledger and implementation checklist.
- `docs/roadmap.md`: sequencing plan.
- `docs/docker.md`: current Docker limitation and target container boundary.

## Current Baseline

The current checkout includes the implementation tree:

- `src/`
- `tests/`
- `scripts/`
- `bridge/`
- `config/`
- `data/fixtures/`

The implemented boundary is fixture-driven Python automation and learning. Do not claim live gameplay automation until Windows local game verification proves it.

## Decisions

- Keep Python `>=3.14`; local `.python-version` is `3.14.5`.
- Replace the old TAS/movie/OCR-first public surface with Python ML/Gymnasium core, C# Godot/Harmony telemetry bridge, and macro-action executor.
- Treat Slay the Spire 2 automation as single-player local research only.
- Forbid online co-op automation, Steam Leaderboards automation, result mutation, anti-cheat bypass, memory writes, and network-match automation.
- Keep the model at the macro-action level; it must not learn raw mouse coordinates.

## Public Commands

These commands are implemented for fixture/local workflows:

- `bridge-smoke`: validate telemetry fixtures.
- `env-step`: run one Gymnasium-style step from a snapshot and macro action index.
- `collect-demo`: collect heuristic demonstrations.
- `train-bc`: train behavioral cloning.
- `train-ppo`: run a MaskablePPO-shaped legal-action smoke path.
- `evaluate-policy`: evaluate BC policies.
- `act`: convert one macro action into a dry-run or native input plan.
- `run-local`: run fixture environment, policy, dataset logging, and executor boundary together.

Retired public commands: `tas-probe`, `tas-record`, `tas-replay`, `tas-verify`, `tas-search`, and OCR-first `live-step`/`live-learn-loop`.

## Target Python Modules

- `telemetry_schema.py`: `TelemetrySnapshot`, `PlayerState`, `CardState`, `EnemyState`, `RelicState`, `PotionState`, `ValidAction`, `MacroAction`, `MacroActionCommand`, `RunRecord`.
- `telemetry_client.py`: stream client boundary for named pipe/WebSocket adapters, reconnect accounting, schema validation, corrupt/duplicate/out-of-order frame rejection.
- `env.py`: `Sts2Env(gymnasium.Env)` with `reset(seed)`, `step(action)`, and `action_masks()`.
- `action_space.py`: macro-action flatten/unflatten, valid action mask, deterministic action IDs.
- `executor.py`: window-relative `play_card`, `end_turn`, `choose_reward`, `choose_map_node`, `choose_event_option`, `shop_buy`, `shop_remove`.
- `heuristic.py`: combat/reward/map/shop/event/rest baseline policy.
- `bc.py`: torch-backed behavioral cloning training and inference.
- `rl.py`: MaskablePPO-shaped smoke training and evaluation.
- `dataset.py`: JSONL-first logging compatible with SQLite and Parquet export.

## Target Bridge

- `bridge/Sts2TelemetryBridge/` will contain the Godot 4 C#/.NET project.
- `.sln` and `.csproj` should be version-controlled with the bridge.
- Harmony bootstrap should load versioned patch points from `config/patch-points.<game_version>.json`.
- Default transport should be Windows named pipe; WebSocket is optional for tooling.
- The bridge should send `TelemetrySnapshot` and accept validated `MacroActionCommand`.
- Symbol mismatch, schema mismatch, stale target state, or invalid command should produce fail-closed diagnostics.

## Dependencies

Current declared runtime dependencies:

- `numpy`
- `torch`
- `pillow`
- `pyobjc-framework-quartz` on macOS only

Target additions:

- `gymnasium`
- `stable-baselines3`
- `sb3-contrib`
- `pydantic`
- `pandas`
- `pyautogui`
- `pynput`
- `mss`
- `opencv-python`
- `mlflow`

Keep dev/build support for `pytest`, `pytest-cov`, Windows executable workflow, and bridge build/test helpers. Update `uv.lock`, Docker, and the Windows executable workflow when the implementation lands.

## Test Order

- Keep the restored `src/` and `tests/` trees aligned with the documented runtime contract.
- Replace or delete old TAS/movie/OCR-only tests.
- Add telemetry schema tests for required fields, version/seed/phase, valid action validation, malformed frame rejection.
- Add action mask tests for legal-only masks, all-invalid rejection, duplicate deterministic IDs, SB3-compatible `action_masks()`.
- Add env tests for Gymnasium reset/step contracts, invalid actions, terminal reward propagation.
- Add bridge fixture tests for fake C# snapshots, stream transport frames, reconnect, and corrupt frame handling.
- Add executor tests for macro-action input plans, target-window guard, partial failure without dataset append.
- Add heuristic tests for lethal attack priority, block priority, zero-energy end turn, reward/map/shop/event choices.
- Add ML smoke tests for BC and MaskablePPO without illegal action selection.

## Current Verification

These checks are valid now:

```bash
uv lock --check
git diff --check
PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

Windows bridge smoke is required when the live bridge exists: build the C# bridge, run fake telemetry producer, run Python `bridge-smoke`. Real game smoke is required before claiming live automation works.

## Sources

- [Gymnasium PyPI](https://pypi.org/project/gymnasium/)
- [Stable-Baselines3 PyPI](https://pypi.org/project/stable-baselines3/)
- [Stable-Baselines3 install docs](https://stable-baselines3.readthedocs.io/en/master/guide/install.html)
- [MaskablePPO docs](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html)
- [Godot C# docs](https://docs.godotengine.org/en/4.5/tutorials/scripting/c_sharp/c_sharp_basics.html)
