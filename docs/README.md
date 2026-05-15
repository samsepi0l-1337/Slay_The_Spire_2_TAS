# Documentation Index

- [Architecture](architecture.md): Game -> C# telemetry bridge -> Python Gymnasium env/ML -> macro-action executor.
- [Rewrite plan](plan.md): decision record for the complete architecture rewrite, dependencies, tests, and source references.
- [Implemented work](implemented-work.md): target architecture baseline and public-surface checklist.
- [Roadmap](roadmap.md): P0/P1/P2 implementation order for telemetry, Gymnasium, BC, MaskablePPO, experiment tracking, and export work.
- [Docker](docker.md): Python 3.14 container boundary, local data volumes, and why desktop capture/input stays on the host.
- [AGENTS.md](../AGENTS.md): module ownership and path guidance for the telemetry rewrite.

## Current Direction

The repository is moving away from the previous screen/OCR and replay-first direction. The new default is structured telemetry from a C# Godot/Harmony bridge, a Python Gymnasium environment, maskable macro actions, and explicit local-only execution.

## Ownership

`telemetry_schema.py`, `telemetry_client.py`, `env.py`, `action_space.py`, `executor.py`, `heuristic.py`, `bc.py`, `rl.py`, `dataset.py`, and `bridge/Sts2TelemetryBridge` are the new module ownership anchors. `AGENTS.md` is the path guidance source for future implementation work.

## Verification

```bash
PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

If the editable install cannot import the local package in a Python 3.14 checkout, use `PYTHONPATH=src` for verification and then fix the local environment separately.
