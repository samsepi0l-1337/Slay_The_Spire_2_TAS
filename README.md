# StS2 TAS

This repository contains a telemetry-driven ML automation research stack for Slay the Spire 2.

## Current State

The current checkout has the first runnable fixture-based automation and learning stack.

Present files:

- `src/sts2_tas/`: telemetry schema/client, Gymnasium-style env adapter, action masks, dry-run executor, heuristic policy, torch BC/PPO-smoke training, dataset logging, and CLI.
- `tests/`: regression tests for schema, action space, env, executor, heuristic, dataset, ML, and CLI.
- `data/fixtures/`: fixture telemetry and ML smoke records.
- `bridge/Sts2TelemetryBridge/`: minimal .NET bridge project skeleton for fixture smoke.
- `config/`: versioned patch-point fixture config.
- `docs/`: architecture, rewrite plan, roadmap, Docker boundary, and implementation checklist.
- `pyproject.toml`: package metadata, Python `>=3.14`, CLI entry point, and coverage settings.
- `.python-version`: pinned to `3.14.5`.
- `Dockerfile`: Python CLI image.
- `.github/workflows/windows-exe.yml`: Windows executable workflow for the new CLI smoke surface.

The implementation is fixture/local research only. It does not claim live gameplay automation until a Windows local session proves bridge attach, target process detection, valid action masks, dry-run plan, and `--execute` acknowledgement against the actual game.

## Runtime Direction

The target architecture is:

```text
Slay the Spire 2
  -> C# Godot/Harmony telemetry bridge
  -> Python Gymnasium environment and ML policy
  -> macro-action executor
  -> guarded local input only when explicitly enabled
```

The model must choose structured macro actions such as `play_card(hand_slot=2, target_slot=0)`, `end_turn`, or `choose_reward(choice_slot=1)`. It must not learn or emit raw mouse coordinates.

This stack is for single-player local research only. Do not use it for online co-op, Steam Leaderboards, public matchmaking, anti-cheat bypass, game result mutation, memory writes, or network-match automation. Real OS input must remain gated by `--execute`; dry-run planning and structured logs are the default workflow.

## Public Commands

Implemented commands:

- `bridge-smoke --fixture data/fixtures/telemetry-combat.json`
- `env-step --snapshot data/fixtures/telemetry-combat.json --action-index 0`
- `collect-demo --snapshot data/fixtures/telemetry-combat.json --output /tmp/demo.jsonl`
- `train-bc --dataset data/fixtures/ml-train-smoke.jsonl --model /tmp/bc.json`
- `train-ppo --dataset data/fixtures/ml-train-smoke.jsonl --model /tmp/ppo.json --timesteps 2`
- `evaluate-policy --dataset data/fixtures/ml-train-smoke.jsonl --model /tmp/bc.json`
- `act --action-json '{"action_type":"end_turn","args":{}}'`
- `run-local --snapshot data/fixtures/telemetry-combat.json --episodes 1 --output /tmp/run.jsonl`

Retired command families are historical compatibility names. If old source or tests are restored, treat these as debt to remove or replace: `tas-probe`, `tas-record`, `tas-replay`, `tas-verify`, `tas-search`, OCR-first `live-step`, and OCR-first `live-learn-loop`.

## Current Verification

Current verification:

```bash
uv lock --check
git diff --check
PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

## Docs

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/plan.md](docs/plan.md)
- [docs/implemented-work.md](docs/implemented-work.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/docker.md](docs/docker.md)
