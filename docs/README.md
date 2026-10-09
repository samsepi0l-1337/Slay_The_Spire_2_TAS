# Documentation Index

These documents describe the current fixture-based implementation and the current verification boundary for the present live-game mod source.

- [2026-10-09 인계 기록](handoff-2026-10-09.md): 작업 중지 상태, 검증 코드 SHA, 미해결 P1과 재개 순서.
- [Architecture](architecture.md): target runtime contract for the telemetry bridge, Gymnasium environment, ML policy, and macro-action executor.
- [Rewrite plan](plan.md): decision record for the target rewrite, dependencies, test order, and verification gates.
- [Implemented work](implemented-work.md): current implementation ledger and target checklist.
- [Roadmap](roadmap.md): implementation order from repository repair through telemetry, Gymnasium, bridge, ML, and export work.
- [Quality checks](quality-checks.md): reproducible integrated Python/C# gates and evidence limits.
- [Core quality](core-quality.md): snapshot ownership, validation and input-backend corrections.
- [Live quality](live-quality.md): pending transitions, loading/cooldown, transport and rewards.
- [Bridge quality](bridge-quality.md): command eligibility, fixture checks and mod build boundary.
- [ML quality](ml-quality.md): artifact validation and legal-action training behavior.
- [Playbook](playbook.md): manual local game workflow.
- [Docker](docker.md): current Docker limitation and the target container boundary.
- [AGENTS.md](../AGENTS.md): module ownership and path guidance for future implementation work.

## Current Repository State

The current checkout has documentation, packaging metadata, a Dockerfile, a lockfile, tests, fixture data, a Python runtime tree, and a fixture bridge and Godot/Harmony mod source.

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

Also present:

- `bridge/Sts2TasMod/`: Godot/Harmony attach and named-pipe `sts2-tas` source for STS2 `v0.107.1`.
- TCP fixture `pipe-serve`, exercised with Python CLI subprocess E2E.
- [Quality checks](quality-checks.md): reproducible local/CI checks and evidence limits.

Not established by the current fixture checks:

- actual game-process attach, valid live masks and command application in a current Windows game session.
- native Python input backend acknowledgement (currently unsupported).

## Current Direction

The repository is moving away from the previous screen/OCR and replay-first direction. The target default is structured telemetry from a C# Godot/Harmony bridge, a Python Gymnasium environment, maskable macro actions, and explicit local-only execution.

## Ownership

The module ownership anchors are `telemetry_schema.py`, `telemetry_client.py`, `env.py`, `action_space.py`, `executor.py`, `heuristic.py`, `bc.py`, `rl.py`, `qstar.py`, `dataset.py`, and `bridge/Sts2TelemetryBridge`. `AGENTS.md` remains the path guidance source for future implementation work.

## Verification

Current implementation gate:

```bash
uv lock --check
git diff --check
uv run --locked --extra dev ruff check src tests scripts bridge/tests
uv run --locked --extra dev ruff format --check src tests scripts bridge/tests
uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```
