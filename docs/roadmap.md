# Roadmap

## P0: Repair The Repository Baseline

- [x] Create or restore `src/`, `tests/`, `scripts/`, `bridge/`, `config/`, and `data/fixtures/` as needed.
- [x] Replace the legacy Windows workflow references to missing files before relying on CI.
- [x] Make `Dockerfile` build only after the source tree exists, or change it to an explicit placeholder until implementation starts.
- [x] Keep `uv lock --check` and `git diff --check` green.
- [x] Add the first fail-before/pass-after tests for the telemetry schema before runtime implementation.

## P1: Core Python Runtime

- [x] Implement telemetry schema/client with versioned `TelemetrySnapshot` validation and reconnect-aware stream reads.
- [x] Implement Gymnasium-style env with `reset`, `step`, `action_masks`, reward, terminal handling, and deterministic seeds.
- [x] Implement action mask flatten/unflatten in `action_space.py`.
- [x] Implement macro executor with dry-run output, target-window guard, and `--execute` gate.
- [x] Add bridge fixture tests for valid, corrupt, duplicate, out-of-order, and reconnecting stream frames.
- Add dependencies in one lockfile pass: `gymnasium`, `stable-baselines3`, `sb3-contrib`, `pydantic`, `pandas`, `pyautogui`, `pynput`, `mss`, `opencv-python`, and `mlflow`.

## P2: Bridge And Public CLI

- [x] Add C# bridge project under `bridge/Sts2TelemetryBridge` as a fixture smoke skeleton.
- [x] Check in the Godot 4 C# `.sln` and `.csproj` files with the bridge project.
- [x] Add `bridge-smoke`, `env-step`, `collect-demo`, `train-bc`, `train-ppo`, `evaluate-policy`, and `act`.
- [x] Add `run-local` after the smaller commands are stable.
- [x] Replace the Windows executable workflow so it builds the new CLI surface and includes bridge smoke fixtures.

## P3: Policies And Data

- [x] Add heuristic policy for combat, rewards, map, shop, event, and rest phases.
- [x] Add torch-backed behavioral cloning training with demonstration JSONL.
- [x] Add MaskablePPO-shaped smoke training backed by the legal-action BC artifact.
- [x] Add policy evaluation summaries with fixture accuracy metrics.
- Add richer entity encoders for cards, enemies, relics, and map choices.
- Add parallel env collection once one local bridge loop is stable.
- Add transformer policy experiments for larger card/relic/action spaces.
- Add MLflow experiment tracking and Parquet export for larger runs.

## Maintenance

- Keep `AGENTS.md` module ownership current whenever paths move or old runtime surfaces are deleted.
- Keep docs explicit about whether each surface is current, target, or retired.
- Do not present target commands as runnable until a local verification command proves them.

## Acceptance Boundary

Do not claim live game automation works until a Windows local session proves bridge attach, target process detection, valid action masks, dry-run plan, and `--execute` input acknowledgement against the actual game. Unit tests and bridge fixtures prove contracts, not live gameplay success.
