# Roadmap

## P0

- Implement telemetry schema/client with versioned `TelemetrySnapshot` validation.
- Implement Gymnasium env with `reset`, `step`, `action_masks`, reward, terminal handling, and deterministic seeds.
- Implement action mask flatten/unflatten in `action_space.py`.
- Implement macro executor with dry-run JSONL output, target-window guard, and `--execute` gate.
- Add bridge fixture tests for valid, corrupt, duplicate, and out-of-order frames.
- Add `run-local` as the integration command after `bridge-smoke`, `env-step`, `collect-demo`, `train-bc`, `train-ppo`, `evaluate-policy`, and `act` are stable.
- Add dependencies in one lockfile pass: `gymnasium`, `stable-baselines3`, `sb3-contrib`, `pydantic`, `pandas`, `pyautogui`, `pynput`, `mss`, `opencv-python`, and `mlflow`.

## P1

- Add heuristic policy for combat, rewards, map, shop, event, and rest phases.
- Add behavioral cloning training with demonstration JSONL.
- Add MaskablePPO smoke training through `sb3-contrib`.
- Add policy evaluation summaries with win/floor/reward/safety metrics.
- Add C# bridge project under `bridge/Sts2TelemetryBridge` with Harmony bootstrap and named pipe transport.
- Check in the Godot 4 C# `.sln` and `.csproj` files with the bridge project.
- Replace the Windows executable workflow so it builds the new CLI surface and includes bridge smoke fixtures.

## P2

- Add richer entity encoders for cards, enemies, relics, and map choices.
- Add parallel env collection once one local bridge loop is stable.
- Add transformer policy experiments for larger card/relic/action spaces.
- Add MLflow experiment tracking and Parquet export for larger runs.
- Keep `AGENTS.md` module ownership current whenever paths move or old runtime surfaces are deleted.

## Acceptance Boundary

Do not claim live game automation works until a Windows local session proves bridge attach, target process detection, valid action masks, dry-run plan, and `--execute` input acknowledgement against the actual game. Unit tests and bridge fixtures prove contracts, not live gameplay success.
