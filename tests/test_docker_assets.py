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

    assert ".venv/" in patterns
    assert ".omx/" in patterns
    assert "data/" in patterns
    assert "models/" in patterns
    assert ".git/" in patterns


def test_docs_explain_windows_docker_and_v1_gaps() -> None:
    docker_doc = (ROOT / "docs" / "docker.md").read_text(encoding="utf-8")
    gaps_doc = (ROOT / "docs" / "v1-gaps.md").read_text(encoding="utf-8")
    architecture_doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Windows PowerShell" in docker_doc
    assert "Python 3.14" in docker_doc
    assert "docker run --rm" in docker_doc
    assert "volume" in docker_doc
    assert "OCR" in gaps_doc
    assert "screen automation" in gaps_doc
    assert "reinforcement learning" in gaps_doc
    assert "target-window activation" in gaps_doc
    assert "Quartz/PyObjC targeted PID input delivery" in gaps_doc
    assert "window focus management" not in gaps_doc
    assert "Docker" in index
    assert "v1 gaps" in index
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
