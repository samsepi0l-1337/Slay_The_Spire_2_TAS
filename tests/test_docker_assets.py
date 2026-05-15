import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_exposes_cli_entrypoint() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.14-slim" in dockerfile
    assert "pip install --no-cache-dir ." in dockerfile
    assert 'ENTRYPOINT ["sts2-tas"]' in dockerfile
    assert 'CMD ["--help"]' in dockerfile


def test_project_requires_python_314() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["requires-python"] == ">=3.14"


def test_uv_uses_exact_python_patch_on_windows_ssh() -> None:
    python_version = (ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert python_version == "3.14.5"


def test_dockerignore_excludes_local_state_and_generated_outputs() -> None:
    patterns = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    gitignore_patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert ".venv/" in patterns
    assert ".uv-cache/" in patterns
    assert ".omx/" in patterns
    assert "data/" in patterns
    assert "models/" in patterns
    assert ".git/" in patterns
    assert ".uv-cache/" in gitignore_patterns
    assert "dist/" in gitignore_patterns


def test_docs_explain_windows_docker_and_deferred_scope() -> None:
    docker_doc = (ROOT / "docs" / "docker.md").read_text(encoding="utf-8")
    architecture_doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    implemented_doc = (ROOT / "docs" / "implemented-work.md").read_text(encoding="utf-8")
    gaps_doc = (ROOT / "docs" / "v1-gaps.md").read_text(encoding="utf-8")
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "Windows PowerShell" in docker_doc
    assert "Python 3.14" in docker_doc
    assert ".python-version" in docker_doc
    assert "3.14.5" in docker_doc
    assert "untrusted mount point" in docker_doc
    assert "docker run --rm" in docker_doc
    assert "volume" in docker_doc
    assert "TasMovie" in implemented_doc
    assert "TasCheckpoint" in implemented_doc
    assert "TasExperience" in implemented_doc
    assert "Steam/Godot process memory" not in implemented_doc
    assert "PPO, GNN map encoder, simulator-backed self-play" not in implemented_doc
    assert "Detours" in architecture_doc
    assert "Present" in architecture_doc
    assert "input hook" in architecture_doc
    assert "time hook" in architecture_doc
    assert "window focus management" not in implemented_doc
    assert "Docker" in index
    assert "v1-gaps.md" in index
    assert "semantic movie" in index
    assert "PYTHONPATH=src" in index
    assert "tas-verify --runs 5" in architecture_doc
    assert "live Windows `tas-verify --runs 5`" in architecture_doc
    assert "train --label-policy verified" in implemented_doc
    assert "static `tas-replay --verify`" in gaps_doc
    assert "Five-run acceptance" in gaps_doc
    assert "TAS-grade acceptance" in gaps_doc
    assert "화면 인식/입력 MVP" not in gaps_doc
    assert "OCR-first MVP" not in gaps_doc
    assert "PPO" not in gaps_doc
    assert "SlayTheSpire2" in docker_doc
    assert "--tessdata-dir" in docker_doc
    assert "kor.traineddata" in docker_doc
    assert "scripts/run-windows-live-loop.ps1" in docker_doc
    assert "--policy first-legal" in docker_doc
    assert "--stop-file" in docker_doc


def test_windows_live_loop_script_runs_hidden_interactive_task_until_stop_file() -> None:
    script = (ROOT / "scripts" / "run-windows-live-loop.ps1").read_text(encoding="utf-8")

    assert "STS2TASLiveLoop" in script
    assert "Register-ScheduledTask" in script
    assert "-LogonType Interactive" in script
    assert "WindowsIdentity]::GetCurrent().Name" in script
    assert '[ValidateSet("Highest", "Limited")]' in script
    assert "-RunLevel $RunLevel" in script
    assert "Register-ScheduledTask" in script and "-ErrorAction Stop" in script
    assert "-WindowStyle Hidden" in script
    assert "live-learn-loop" in script
    assert '"--target-process", $TargetProcess' in script
    assert '"--input-backend", "native"' in script
    assert '"--execute"' in script
    assert '"--policy", "first-legal"' in script
    assert '"--stop-file", $StopFile' in script
    assert "Sts2Exe" in script
