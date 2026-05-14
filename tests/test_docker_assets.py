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
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Windows PowerShell" in docker_doc
    assert "Python 3.14" in docker_doc
    assert "docker run --rm" in docker_doc
    assert "volume" in docker_doc
    assert "OCR" in implemented_doc
    assert "Steam/Godot process memory" in implemented_doc
    assert "--execute" in implemented_doc
    assert "PPO, GNN map encoder, simulator-backed self-play" in implemented_doc
    assert "self-label" in implemented_doc
    assert "state-derived legal action generator" in implemented_doc
    assert "Quartz/PyObjC targeted PID event delivery" in architecture_doc
    assert "window focus management" not in implemented_doc
    assert "Docker" in index
    assert "v1-gaps.md" in index
    assert "v1-gaps.md" in readme
    assert "allow-model-self-labels" in architecture_doc
    assert "--coordinate-space window_relative" in architecture_doc
    assert "Windows executable" in index
    assert "PYTHONPATH=src" in index
    assert "--no-editable" in index
    assert "scripts/build-windows-exe.ps1" in readme
    assert "sts2-tas-windows-x64" in readme
    assert "dist/sts2-tas.exe" in readme
    assert "PYTHONPATH=src" in readme
    assert "--no-editable" in readme
    assert (
        'live-step --screenshot-out live.png --ocr-provider tesseract --choice pick_card:strike '
        "--input-log inputs.jsonl"
    ) in readme
    assert '--target-process "Slay the Spire 2" --input-backend native --execute' in readme
    assert (
        'live-step --screenshot-out ... --target-process "Slay the Spire 2" '
        "--input-backend native --execute"
    ) in architecture_doc
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
    assert "--target-process $TargetProcess" in script
    assert "--input-backend native" in script
    assert "--execute" in script
    assert "--policy first-legal" in script
    assert "--stop-file $StopFile" in script
