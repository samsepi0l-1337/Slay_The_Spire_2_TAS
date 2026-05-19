# Documentation Index

These documents describe the current fixture-based implementation and the remaining live-game bridge work.

- [Architecture](architecture.md): target runtime contract for the telemetry bridge, Gymnasium environment, ML policy, and macro-action executor.
- [Rewrite plan](plan.md): decision record for the target rewrite, dependencies, test order, and verification gates.
- [Implemented work](implemented-work.md): current implementation ledger and target checklist.
- [Roadmap](roadmap.md): implementation order from repository repair through telemetry, Gymnasium, bridge, ML, and export work.
- [Docker](docker.md): current Docker limitation and the target container boundary.
- [AGENTS.md](../AGENTS.md): module ownership and path guidance for future implementation work.

## Current Repository State

The current checkout has documentation, packaging metadata, a Dockerfile, a lockfile, tests, fixture data, a Python runtime tree, and a minimal bridge project skeleton.

Present:

- `README.md`
- `docs/*.md`
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `Dockerfile`
- `src/sts2_tas/`
- `tests/`
- `scripts/build-windows-exe.ps1`
- `data/fixtures/`
- `config/patch-points.0.1-test.json`
- `bridge/Sts2TelemetryBridge/`
- `.github/workflows/windows-exe.yml`

Absent:

- live Godot/Harmony patch attach against a real Slay the Spire 2 process
- production named-pipe transport
- real-game Windows `--execute` acknowledgement

## Current Direction

The repository is moving away from the previous screen/OCR and replay-first direction. The target default is structured telemetry from a C# Godot/Harmony bridge, a Python Gymnasium environment, maskable macro actions, and explicit local-only execution.

## Ownership

The module ownership anchors are `telemetry_schema.py`, `telemetry_client.py`, `env.py`, `action_space.py`, `executor.py`, `heuristic.py`, `bc.py`, `rl.py`, `dataset.py`, and `bridge/Sts2TelemetryBridge`. `AGENTS.md` remains the path guidance source for future implementation work.

## Verification

Current implementation gate:

```bash
uv lock --check
git diff --check
PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```
