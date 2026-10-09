# Quality checks

Use Python 3.14, uv and the .NET 8 SDK. The fixture bridge does not require game assemblies.

```bash
uv lock --check
uv sync --locked --extra dev
uv run --locked --extra dev ruff check src tests scripts bridge/tests
uv run --locked --extra dev ruff format --check src tests scripts bridge/tests
uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100
dotnet run --project bridge/tests/EventChoices/EventChoices.csproj -c Release
dotnet format whitespace bridge/Sts2TelemetryBridge/Sts2TelemetryBridge.csproj --verify-no-changes --no-restore
dotnet format whitespace bridge/tests/EventChoices/EventChoices.csproj --verify-no-changes --no-restore
git diff --check
```

Ruff is pinned in the dev extra and lockfile. Rules cover import ordering, undefined names, unused imports and basic syntax errors. Format with `uv run --locked --extra dev ruff format src tests scripts bridge/tests` after edits.

`tests/test_cli_e2e.py` runs real Python CLI subprocesses for fixture validation, demonstration collection, BC training/evaluation and Q* output persistence. It also builds the C# fixture bridge and connects the live CLI to its TCP producer. There is no optional skip for a missing SDK: install .NET 8 before running the full suite. `data/fixtures/` is tracked and available in fresh checkouts.

The full pytest discovery also includes `bridge/tests/test_bridge.py`, covering real C# legal/rejected commands and malformed listeners. The separate native EventChoices harness verifies compact-to-original button eligibility mapping and stable/distinct/null run-object identities. C# whitespace gates cover both fixture and helper projects.

The quality workflow runs on Linux and Windows. The quality workflow parses every PowerShell script without executing launch, checkout or trust operations. The Windows executable workflow checks each native process exit before artifact upload. Neither workflow deploys a mod, attaches to a game, or sends game input. A transport fixture command is not an acknowledgement that a real game applied an action.

CLI syntax errors return `2`. Expected input, filesystem, transport and unavailable-backend errors return `1` with stderr diagnostics. Keyboard interruption returns `130`. Unexpected programming exceptions remain visible. Live CLI transport handles close on success/failure, including a reader-close exception; shared named-pipe handles close once.

Native Python input remains unsupported and enabled calls fail closed. The repository contains Godot/Harmony mod and named-pipe source, but a current Windows game session must separately verify attach, process/window identity, legal masks and actual command application before claiming live gameplay success. SSH or CI fixture results alone do not establish those facts.

Docker uses the tracked lockfile and pinned uv release for CLI dependencies. Image build/run must be verified separately when Docker is available; Python/C# tests do not prove an image build.

Windows launch helpers refuse dirty repositories and unexpected branches before fast-forward updates; they never force checkout/reset. Mod deployment is explicit (`-p:DeployMod=true`) in launch helpers only. They do not create certificates, import trusted publishers or unblock binaries; existing project/system trust is preserved.

## Observed local evidence (2026-10-09)

- Before the CLI repair: `uv run --extra dev pytest tests/test_cli_and_ml.py -q` produced `2 failed, 14 passed`; missing fixture and unsupported execution escaped instead of returning `1`. The interruption test aborted the baseline with exit `2`.
- After the repair: `uv run --extra dev pytest tests/test_cli_and_ml.py tests/test_cli_e2e.py -q` produced `23 passed in 13.69s`, including the real C# TCP producer/CLI subprocess pair.
- Full local suite: `uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100 -q` produced `75 passed in 9.73s`, 100.00% coverage (1109 statements, zero missed). `uv lock --check`, `git diff --check` and Ruff checks on owned Python files passed.
- These observations are macOS fixture results. Windows SSH, current game-session behavior and Docker image verification are separate checks; this record does not claim them completed.

## Integrated local verification (2026-10-09)

After the core, ML, live and producer follow-ups were combined:

- `uv run --locked --extra dev pytest --cov=sts2_tas --cov-fail-under=100 -q`: `173 passed, 16 subtests passed in 18.51s`; 100.00% coverage, 1192 statements, zero missed.
- `uv run --locked --extra dev ruff check src tests scripts bridge/tests`: passed.
- `uv run --locked --extra dev ruff format --check src tests scripts bridge/tests`: 27 files already formatted.
- Native EventChoices/RunIdentity harness: both `PASS`; fixture/helper C# whitespace verification passed.
- `uv lock --check`, `git diff --check` and a source/test/script line-count inspection passed; all Python/C#/PowerShell files are at most 400 lines, excluding generated build files.
- Python runtime formatting preserved the parsed AST. Windows PowerShell parsing is wired into CI but was not executed locally because `pwsh` is unavailable. Windows SSH and actual game validation remain separate coordinator checks.
- `docker info` failed because `/Users/samsepiol/.docker/run/docker.sock` was absent; no image-build success is claimed.
