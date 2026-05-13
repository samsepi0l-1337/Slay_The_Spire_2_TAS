import tomllib
from pathlib import Path
import runpy

import pytest
import sts2_tas.cli


ROOT = Path(__file__).resolve().parents[1]


def test_project_exposes_module_entrypoint_for_freezers() -> None:
    entrypoint = (ROOT / "src" / "sts2_tas" / "__main__.py").read_text(encoding="utf-8")

    assert "from sts2_tas.cli import main" in entrypoint
    assert "raise SystemExit(main())" in entrypoint


def test_module_entrypoint_calls_cli_main(monkeypatch) -> None:
    monkeypatch.setattr(sts2_tas.cli, "main", lambda: 12)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("sts2_tas.__main__", run_name="__main__")

    assert exit_info.value.code == 12


def test_windows_exe_build_script_uses_pyinstaller_onefile() -> None:
    script = (ROOT / "scripts" / "build-windows-exe.ps1").read_text(encoding="utf-8")

    assert "uv sync --extra build" in script
    assert "pyinstaller" in script
    assert "--onefile" in script
    assert "--console" in script
    assert "src/sts2_tas/__main__.py" in script
    assert "dist/sts2-tas.exe" in script


def test_github_actions_builds_windows_exe_artifact() -> None:
    workflow = (ROOT / ".github" / "workflows" / "windows-exe.yml").read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "scripts/build-windows-exe.ps1" in workflow
    assert "dist/sts2-tas.exe" in workflow
    assert "sts2-tas-windows-x64" in workflow


def test_pyinstaller_is_a_build_extra() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert any(dep.startswith("pyinstaller") for dep in pyproject["project"]["optional-dependencies"]["build"])
