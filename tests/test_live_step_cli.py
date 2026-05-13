import json
from pathlib import Path

from PIL import Image
from PIL import ImageGrab
import pytest

from sts2_tas import cli, runtime


def _screen(path: Path) -> Path:
    Image.new("RGB", (1920, 1080), (15, 18, 24)).save(path)
    return path


def _ocr_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {"text": "타격", "box": [250, 260, 430, 330], "confidence": 0.99},
                {"text": "수비", "box": [760, 260, 940, 330], "confidence": 0.99},
                {"text": "강타", "box": [1270, 260, 1450, 330], "confidence": 0.99},
                {"text": "넘기기", "box": [880, 930, 1040, 990], "confidence": 0.99},
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_cli_live_step_with_fixture_choice_reports_verifiable_action(tmp_path: Path, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--character",
            "ironclad",
            "--ascension",
            "0",
            "--floor",
            "1",
            "--hp",
            "70",
            "--gold",
            "0",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["choice"] == {"action": "pick", "option_id": "strike"}
    assert output["action"]["dry_run"] is True
    assert output["action"]["input_plan"] == {"kind": "click", "x": 340, "y": 295}
    assert output["screenshot_path"] == str(tmp_path / "screen.png")
    assert not input_log.exists()


def test_cli_live_step_with_model_recommendation_executes_jsonl(tmp_path: Path, monkeypatch, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"

    class Result:
        best = type("Best", (), {"action": "skip", "option_id": "skip", "score": 0.9})()
        candidates = []

    monkeypatch.setattr(cli, "load_model", lambda path: object())
    monkeypatch.setattr(cli, "recommend", lambda model, snapshot: Result())

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--model",
            str(tmp_path / "model.joblib"),
            "--input-log",
            str(input_log),
            "--execute",
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--character",
            "ironclad",
            "--ascension",
            "0",
            "--floor",
            "1",
            "--hp",
            "70",
            "--gold",
            "0",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    event = json.loads(input_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert output["choice"] == {"action": "skip", "option_id": None}
    assert event["input_plan"] == {"kind": "click", "x": 960, "y": 960}


def test_cli_live_step_captures_screen_with_injected_grabber(tmp_path: Path, monkeypatch, capsys) -> None:
    screenshot_out = tmp_path / "live.png"

    def fake_capture(path: Path) -> Path:
        return _screen(path)

    monkeypatch.setattr(cli, "capture_screen", fake_capture)

    exit_code = cli.main(
        [
            "live-step",
            "--screenshot-out",
            str(screenshot_out),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--choice",
            "skip",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--character",
            "ironclad",
            "--ascension",
            "0",
            "--floor",
            "1",
            "--hp",
            "70",
            "--gold",
            "0",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["choice"] == {"action": "skip", "option_id": None}
    assert output["screenshot_path"] == str(screenshot_out)


def test_capture_screen_uses_injected_grabber(tmp_path: Path) -> None:
    screenshot = tmp_path / "screen.png"

    class GrabbedImage:
        def save(self, path: Path) -> None:
            Image.new("RGB", (4, 3), (1, 2, 3)).save(path)

    result = runtime.capture_screen(screenshot, grabber=lambda: GrabbedImage())

    assert result == screenshot
    assert Image.open(screenshot).size == (4, 3)


def test_capture_screen_uses_pillow_grabber_without_real_screen(tmp_path: Path, monkeypatch) -> None:
    screenshot = tmp_path / "screen.png"
    monkeypatch.setattr(ImageGrab, "grab", lambda: Image.new("RGB", (5, 6), (4, 5, 6)))

    result = runtime.capture_screen(screenshot)

    assert result == screenshot
    assert Image.open(screenshot).size == (5, 6)


def test_capture_screen_reports_permission_failure(tmp_path: Path) -> None:
    def failing_grabber():
        raise OSError("permission denied")

    with pytest.raises(RuntimeError, match="screen recording permission"):
        runtime.capture_screen(tmp_path / "screen.png", grabber=failing_grabber)


def test_cli_live_step_rejects_native_without_execute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --execute"):
        cli.main(
            [
                "live-step",
                "--capture-fixture",
                str(_screen(tmp_path / "screen.png")),
                "--ocr-fixture",
                str(_ocr_fixture(tmp_path / "ocr.json")),
                "--choice",
                "pick:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
                "--input-backend",
                "native",
                "--game-version",
                "0.105.1",
                "--branch",
                "beta",
                "--character",
                "ironclad",
                "--ascension",
                "0",
                "--floor",
                "1",
                "--hp",
                "70",
                "--gold",
                "0",
            ]
        )
