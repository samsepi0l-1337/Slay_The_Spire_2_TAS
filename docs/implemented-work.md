# Implementation Ledger

## Current State

This repository now contains the first fixture-based runtime source tree, tests, bridge project skeleton, build script, patch-point config, and telemetry fixtures.

Implemented or present:

- [x] Documentation set under `docs/`
- [x] Root `README.md`
- [x] Python metadata in `pyproject.toml`
- [x] Python version pin in `.python-version`
- [x] `uv.lock`
- [x] Dockerfile skeleton
- [x] Windows executable workflow file for the new CLI smoke surface
- [x] `src/sts2_tas/`
- [x] `tests/`
- [x] `scripts/build-windows-exe.ps1`
- [x] `bridge/Sts2TelemetryBridge`
- [x] `config/patch-points.0.1-test.json`
- [x] `data/fixtures/`

Not present:

- [ ] live Godot/Harmony attach against the actual game process
- [ ] production named-pipe transport
- [ ] real Windows `--execute` acknowledgement against Slay the Spire 2

## Target Public Commands

- [x] `bridge-smoke`: load a telemetry fixture and validate schema compatibility.
- [x] `env-step`: run one Gymnasium-style environment step from a snapshot and macro action index.
- [x] `collect-demo`: collect heuristic demonstrations into JSONL.
- [x] `train-bc`: train a behavioral cloning policy from demonstrations.
- [x] `train-ppo`: run a MaskablePPO-shaped smoke path backed by the legal-action BC table.
- [x] `evaluate-policy`: evaluate a BC policy against recorded fixture transitions.
- [x] `act`: convert a macro action into a dry-run or `--execute` input plan.
- [x] `run-local`: run a fixture snapshot, policy choice, environment step, dataset logging, and dry-run executor boundary.

## Target Python Modules

- [x] `telemetry_schema.py`: typed state, `TelemetrySnapshot`, `ValidAction`, `MacroAction`, validation.
- [x] `telemetry_client.py`: frame reader plus stream client with reconnect counting, corrupt-frame, duplicate, and out-of-order rejection.
- [x] `env.py`: Gymnasium-style adapter with `reset`, `step`, `action_masks`, reward, terminal handling.
- [x] `action_space.py`: deterministic flatten/unflatten and mask generation.
- [x] `executor.py`: guarded dry-run and `--execute`-gated macro-action execution plan.
- [x] `heuristic.py`: baseline combat/reward/map/shop/event/rest policy.
- [x] `bc.py`: torch-backed behavioral cloning training and valid-action scoring, with legacy JSON table compatibility.
- [x] `rl.py`: MaskablePPO-shaped smoke training path backed by the legal-action BC artifact.
- [x] `dataset.py`: JSONL first, SQLite/Parquet compatible transition records.

## Target Bridge Surface

- [x] `bridge/Sts2TelemetryBridge`: minimal .NET C# project skeleton.
- [x] `.sln` and `.csproj`: checked in with the bridge project so build shape is versioned.
- [ ] Harmony bootstrap for real game versioned patch points.
- [x] `patch-points.<game_version>.json`: fixture inspected symbols and source assumptions.
- [ ] Named pipe default transport and optional WebSocket transport.
- [x] `MacroActionCommand`: Python-to-bridge command envelope for validated executor requests.
- [x] Schema-versioned fixture smoke and fail-closed config.

## Current Dependency Contract

Currently declared runtime dependencies:

- [x] `numpy`
- [x] `pillow`
- [x] `torch`
- [x] `pyobjc-framework-quartz` on macOS only

Currently declared dev/build dependencies:

- [x] `pytest`
- [x] `pytest-cov`
- [x] `pyinstaller`

Target dependencies not yet declared:

- [ ] `gymnasium`
- [ ] `stable-baselines3`
- [ ] `sb3-contrib`
- [ ] `pydantic`
- [ ] `pandas`
- [ ] `pyautogui`
- [ ] `pynput`
- [ ] `mss`
- [ ] `opencv-python`
- [ ] `mlflow`

## Safety Checklist

- [x] Single-player/local research wording appears in README and architecture docs.
- [x] Online co-op and Steam Leaderboards automation are explicitly forbidden.
- [x] Native input is documented as gated by `--execute`.
- [x] The model is documented as never predicting raw mouse coordinates.
- [x] Runtime implementation enforces `--execute`.
- [x] Invalid action masks fail closed in code.
- [x] Runtime logs include enough state/action/reward context for audit and replay of decisions.
