# Target Architecture Baseline

## Not Current Implementation

This document intentionally describes the target public surface for the rewrite, not a claim that every item is already implemented. Existing code still contains old runtime paths until later implementation phases remove them.

## Target Public Commands

- [ ] `bridge-smoke`: load a telemetry fixture or local bridge frame and validate schema compatibility.
- [ ] `env-step`: run one Gymnasium-style environment step from a snapshot and macro action.
- [ ] `collect-demo`: collect human or heuristic demonstrations into JSONL.
- [ ] `train-bc`: train a behavioral cloning policy from demonstrations.
- [ ] `train-ppo`: fine-tune with MaskablePPO and valid action masks.
- [ ] `evaluate-policy`: evaluate BC/PPO/heuristic policies against recorded episodes.
- [ ] `act`: convert a macro action or policy choice into a dry-run or `--execute` input plan.
- [ ] `run-local`: run the local bridge, policy, environment step loop, dataset logging, and dry-run/native executor boundary in one command.

## Target Python Modules

- [ ] `telemetry_schema.py`: typed state, `TelemetrySnapshot`, `ValidAction`, `MacroAction`, validation.
- [ ] `telemetry_client.py`: named pipe/WebSocket transport, reconnect, frame ordering, corrupt-frame rejection.
- [ ] `env.py`: Gymnasium `Env` adapter with `reset`, `step`, `action_masks`, reward, terminal handling.
- [ ] `action_space.py`: deterministic flatten/unflatten and mask generation.
- [ ] `executor.py`: guarded window-relative macro-action execution.
- [ ] `heuristic.py`: baseline combat/reward/map/shop/event/rest policy.
- [ ] `bc.py`: behavioral cloning training and inference.
- [ ] `rl.py`: MaskablePPO training and evaluation.
- [ ] `dataset.py`: JSONL first, SQLite/Parquet compatible transition logging.

## Target Bridge Surface

- [ ] `bridge/Sts2TelemetryBridge`: Godot .NET C# project.
- [ ] `.sln` and `.csproj`: checked in with the bridge project so Godot 4 C#/.NET build shape is versioned.
- [ ] Harmony bootstrap for versioned patch points.
- [ ] `patch-points.<game_version>.json` records inspected symbols and source assumptions.
- [ ] Named pipe default transport and optional WebSocket transport.
- [ ] `MacroActionCommand`: Python-to-bridge command envelope for validated executor requests.
- [ ] Schema-versioned frame emission and fail-closed diagnostics.

## Dependency Contract

- [ ] Keep: `numpy`, `torch`, `pillow`.
- [ ] Add: `gymnasium`, `stable-baselines3`, `sb3-contrib`, `pydantic`, `pandas`, `pyautogui`, `pynput`, `mss`, `opencv-python`, `mlflow`.
- [ ] Keep dev/build: `pytest`, `pytest-cov`, Windows executable workflow, bridge build/test helpers.
- [ ] Update `uv.lock`, Docker, and Windows executable workflow when the implementation lands.

## Safety Checklist

- [ ] Single-player/local research wording appears in README and architecture docs.
- [ ] Online co-op and Steam Leaderboards automation are explicitly forbidden.
- [ ] Native input remains gated by `--execute`.
- [ ] The model never predicts raw mouse coordinates.
- [ ] Invalid action masks fail closed.
- [ ] Runtime logs include enough state/action/reward context for audit and replay of decisions.
