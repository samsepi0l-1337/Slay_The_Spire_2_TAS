# Rewrite Plan

This document records the full architecture rewrite target. `docs/architecture.md` is the runtime contract, `docs/implemented-work.md` is the implementation checklist, and `docs/roadmap.md` is the sequencing plan.

## Decisions

- Keep Python `>=3.14`.
- Replace the old TAS/movie/OCR-first public surface with Python ML/Gymnasium core, C# Godot/Harmony telemetry bridge, and macro-action executor.
- Treat Slay the Spire 2 automation as single-player local research only.
- Forbid online co-op automation, Steam Leaderboards automation, result mutation, anti-cheat bypass, memory writes, and network-match automation.
- Keep the model at the macro-action level; it must not learn raw mouse coordinates.

## Public Commands

- `bridge-smoke`: validate telemetry fixtures or live bridge frames.
- `env-step`: run one Gymnasium-style step from a snapshot and macro action.
- `collect-demo`: collect human or heuristic demonstrations.
- `train-bc`: train behavioral cloning.
- `train-ppo`: train or fine-tune MaskablePPO.
- `evaluate-policy`: evaluate BC/PPO/heuristic policies.
- `act`: convert one macro action or policy decision into a dry-run or native input plan.
- `run-local`: run the local bridge, environment, policy, dataset logging, and executor boundary together.

Retired public commands: `tas-probe`, `tas-record`, `tas-replay`, `tas-verify`, `tas-search`, and OCR-first `live-step`/`live-learn-loop`.

## Python Modules

- `telemetry_schema.py`: `TelemetrySnapshot`, `PlayerState`, `CardState`, `EnemyState`, `RelicState`, `PotionState`, `ValidAction`, `MacroAction`, `MacroActionCommand`, `RunRecord`.
- `telemetry_client.py`: named pipe/WebSocket client, reconnect, schema validation, corrupt/duplicate/out-of-order frame rejection.
- `env.py`: `Sts2Env(gymnasium.Env)` with `reset(seed)`, `step(action)`, and `action_masks()`.
- `action_space.py`: macro-action flatten/unflatten, valid action mask, deterministic action IDs.
- `executor.py`: window-relative `play_card`, `end_turn`, `choose_reward`, `choose_map_node`, `choose_event_option`, `shop_buy`, `shop_remove`.
- `heuristic.py`: combat/reward/map/shop/event/rest baseline policy.
- `bc.py`: behavioral cloning training and inference.
- `rl.py`: MaskablePPO training and evaluation.
- `dataset.py`: JSONL-first logging compatible with SQLite and Parquet export.

## Bridge

- `bridge/Sts2TelemetryBridge/` contains the Godot 4 C#/.NET project.
- `.sln` and `.csproj` are version-controlled with the bridge.
- Harmony bootstrap loads versioned patch points from `config/patch-points.<game_version>.json`.
- Default transport is Windows named pipe; WebSocket is optional for tooling.
- The bridge sends `TelemetrySnapshot` and accepts validated `MacroActionCommand`.
- Symbol mismatch, schema mismatch, stale target state, or invalid command produces fail-closed diagnostics.

## Dependencies

- Keep: `numpy`, `torch`, `pillow`.
- Add: `gymnasium`, `stable-baselines3`, `sb3-contrib`, `pydantic`, `pandas`, `pyautogui`, `pynput`, `mss`, `opencv-python`, `mlflow`.
- Keep dev/build: `pytest`, `pytest-cov`, Windows executable workflow, bridge build/test helpers.
- Update `uv.lock`, Docker, and the Windows executable workflow with the implementation.

## Test Order

- Replace or delete old TAS/movie/OCR-only tests.
- Add telemetry schema tests for required fields, version/seed/phase, valid action validation, malformed frame rejection.
- Add action mask tests for legal-only masks, all-invalid rejection, duplicate deterministic IDs, SB3-compatible `action_masks()`.
- Add env tests for Gymnasium reset/step contracts, invalid actions, terminal reward propagation.
- Add bridge fixture tests for fake C# snapshots, named pipe/WebSocket frames, reconnect, and corrupt frame handling.
- Add executor tests for macro-action input plans, target-window guard, partial failure without dataset append.
- Add heuristic tests for lethal attack priority, block priority, zero-energy end turn, reward/map/shop/event choices.
- Add ML smoke tests for BC and MaskablePPO without illegal action selection.

## Verification

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
uv lock --check
git diff --check
```

Windows bridge smoke is required when the bridge exists: build the C# bridge, run fake telemetry producer, run Python `bridge-smoke`. Real game smoke is required before claiming live automation works.

## Sources

- [Gymnasium PyPI](https://pypi.org/project/gymnasium/)
- [Stable-Baselines3 PyPI](https://pypi.org/project/stable-baselines3/)
- [Stable-Baselines3 install docs](https://stable-baselines3.readthedocs.io/en/master/guide/install.html)
- [MaskablePPO docs](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html)
- [Godot C# docs](https://docs.godotengine.org/en/4.5/tutorials/scripting/c_sharp/c_sharp_basics.html)
