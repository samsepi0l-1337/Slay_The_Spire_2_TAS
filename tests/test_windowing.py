import pytest

from sts2_tas import windowing
from sts2_tas.schema import TargetWindow
from sts2_tas.windowing import WindowBounds, WindowDetector


def test_window_detector_parses_single_macos_window() -> None:
    commands = []

    def runner(command: list[str]) -> str:
        commands.append(command)
        return "Slay the Spire 2\tMain Window\t100\t200\t1280\t720\n"

    detector = WindowDetector(platform_name="Darwin", runner=runner)

    window = detector.detect("Slay the Spire 2")

    assert window.process == "Slay the Spire 2"
    assert window.title == "Main Window"
    assert window.bounds == WindowBounds(left=100, top=200, width=1280, height=720)
    assert commands[0][0] == "osascript"
    assert "Slay the Spire 2" in commands[0][-1]


def test_window_detector_parses_single_windows_window() -> None:
    commands = []

    def runner(command: list[str]) -> str:
        commands.append(command)
        return "Slay the Spire 2\tMain Window\t100\t200\t1280\t720\n"

    detector = WindowDetector(platform_name="Windows", runner=runner)

    window = detector.detect("Slay the Spire 2")

    assert window.process == "Slay the Spire 2"
    assert window.title == "Main Window"
    assert window.bounds == WindowBounds(left=100, top=200, width=1280, height=720)
    assert commands[0][:3] == ["powershell", "-NoProfile", "-Command"]
    assert "Get-Process" in commands[0][-1]
    assert "GetWindowRect" in commands[0][-1]
    assert "MainWindowTitle -eq $query" in commands[0][-1]
    assert "Slay the Spire 2" in commands[0][-1]


def test_window_detector_escapes_windows_process_query() -> None:
    commands = []
    detector = WindowDetector(
        platform_name="Windows",
        runner=lambda command: commands.append(command) or "Bob's Game\tMain\t1\t2\t3\t4\n",
    )

    detector.detect("Bob's Game")

    assert "Bob''s Game" in commands[0][-1]


def test_window_detector_fails_closed_for_missing_ambiguous_or_bad_bounds() -> None:
    cases = [
        "",
        "Slay the Spire 2\tOne\t0\t0\t1280\t720\nSlay the Spire 2\tTwo\t0\t0\t1280\t720\n",
        "Slay the Spire 2\tBad\t0\t0\t0\t720\n",
        "Slay the Spire 2\tBad\tleft\t0\t1280\t720\n",
    ]

    for output in cases:
        detector = WindowDetector(platform_name="Darwin", runner=lambda command, output=output: output)
        with pytest.raises(RuntimeError):
            detector.detect("Slay the Spire 2")


def test_window_detector_fails_closed_for_invalid_columns_and_process_mismatch() -> None:
    cases = [
        "Slay the Spire 2\tMain\t100\n",
        "Other Game\tMain\t100\t200\t1280\t720\n",
    ]

    for output in cases:
        detector = WindowDetector(platform_name="Darwin", runner=lambda command, output=output: output)
        with pytest.raises(RuntimeError):
            detector.detect("Slay the Spire 2")


def test_window_detector_accepts_bytes_runner_output() -> None:
    detector = WindowDetector(
        platform_name="Darwin",
        runner=lambda command: b"Slay the Spire 2\tMain Window\t100\t200\t1280\t720\n",
    )

    assert detector.detect("Slay the Spire 2").bounds.to_bbox() == (100, 200, 1380, 920)


def test_run_osascript_uses_text_output(monkeypatch) -> None:
    calls = []

    def fake_check_output(command: list[str], text: bool) -> str:
        calls.append((command, text))
        return "ok"

    monkeypatch.setattr(windowing.subprocess, "check_output", fake_check_output)

    assert windowing._run_osascript(["osascript", "-e", "return 1"]) == "ok"
    assert calls == [(["osascript", "-e", "return 1"], True)]


def test_window_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="positive width"):
        WindowBounds(left=0, top=0, width=0, height=10)
    with pytest.raises(ValueError, match="process is required"):
        TargetWindow(process="", title="Main", bounds=WindowBounds(left=0, top=0, width=1, height=1))
    with pytest.raises(ValueError, match="title is required"):
        TargetWindow(process="Slay the Spire 2", title="", bounds=WindowBounds(left=0, top=0, width=1, height=1))


def test_window_detector_rejects_unsupported_platform() -> None:
    detector = WindowDetector(platform_name="Linux", runner=lambda command: "")

    with pytest.raises(RuntimeError, match="target window detection is only supported on macOS or Windows"):
        detector.detect("Slay the Spire 2")
