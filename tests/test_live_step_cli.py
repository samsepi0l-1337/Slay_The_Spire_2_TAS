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


def test_cli_live_step_rejects_capture_fixture_target_window_translation(tmp_path: Path, monkeypatch) -> None:
    class Detector:
        def detect(self, process: str):
            from sts2_tas.schema import TargetWindow, WindowBounds

            assert process == "Slay the Spire 2"
            return TargetWindow(
                process=process,
                title="Main Window",
                bounds=WindowBounds(left=100, top=200, width=1280, height=720),
            )

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    with pytest.raises(ValueError, match="window_relative"):
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
                "--target-process",
                "Slay the Spire 2",
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


def test_cli_live_step_captures_target_window_bbox(tmp_path: Path, monkeypatch, capsys) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    capture_calls = []

    class Detector:
        def detect(self, process: str):
            return TargetWindow(
                process=process,
                title="Main Window",
                bounds=WindowBounds(left=100, top=200, width=1280, height=720),
            )

    def fake_capture(path: Path, *, bbox):
        capture_calls.append((path, bbox))
        return _screen(path)

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())
    monkeypatch.setattr(cli, "capture_screen", fake_capture)

    exit_code = cli.main(
        [
            "live-step",
            "--screenshot-out",
            str(tmp_path / "target.png"),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--choice",
            "skip",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--target-process",
            "Slay the Spire 2",
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
    assert capture_calls == [(tmp_path / "target.png", (100, 200, 1380, 920))]
    assert output["target_window"]["process"] == "Slay the Spire 2"
    assert output["action"]["coordinate_space"] == "window_relative"
    assert output["input_plan"] == {"kind": "click", "x": 1060, "y": 1160}


def test_cli_act_rejects_target_process_for_legacy_screen_absolute_snapshot(tmp_path: Path, monkeypatch) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        '{"game_version":"0.105.1","branch":"beta","character":"ironclad","ascension":0,"floor":1,'
        '"deck":["strike"],"relics":[],"hp":70,"gold":0,'
        '"options":[{"id":"strike","name":"Strike","kind":"card","tags":[],"box":[250,260,430,330]},'
        '{"id":"skip","name":"Skip","kind":"skip","tags":[],"box":[880,930,1040,990]}],'
        '"chosen":null,"skipped":false,"screenshot_path":"screen.png"}',
        encoding="utf-8",
    )
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

    class Detector:
        def detect(self, process: str):
            assert process == "Slay the Spire 2"
            return target_window

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    with pytest.raises(ValueError, match="window_relative"):
        cli.main(
            [
                "act",
                "--snapshot",
                str(snapshot_path),
                "--choice",
                "pick:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
                "--target-process",
                "Slay the Spire 2",
            ]
        )


def test_cli_act_translates_window_relative_snapshot_once(tmp_path: Path, monkeypatch, capsys) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "game_version": "0.105.1",
                "branch": "beta",
                "character": "ironclad",
                "ascension": 0,
                "floor": 1,
                "deck": ["strike"],
                "relics": [],
                "hp": 70,
                "gold": 0,
                "options": [
                    {"id": "strike", "name": "Strike", "kind": "card", "tags": [], "box": [250, 260, 430, 330]},
                    {"id": "skip", "name": "Skip", "kind": "skip", "tags": [], "box": [880, 930, 1040, 990]},
                ],
                "chosen": None,
                "skipped": False,
                "screenshot_path": "screen.png",
                "coordinate_space": "window_relative",
                "target_window": target_window.to_dict(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    class Detector:
        def detect(self, process: str):
            assert process == "Slay the Spire 2"
            return target_window

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    exit_code = cli.main(
        [
            "act",
            "--snapshot",
            str(snapshot_path),
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--target-process",
            "Slay the Spire 2",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["input_plan"] == {"kind": "click", "x": 440, "y": 495}
    assert output["target_window"] == target_window.to_dict()
    assert output["coordinate_space"] == "window_relative"


def test_cli_act_rejects_window_relative_snapshot_without_target_process(tmp_path: Path) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "game_version": "0.105.1",
                "branch": "beta",
                "character": "ironclad",
                "ascension": 0,
                "floor": 1,
                "deck": ["strike"],
                "relics": [],
                "hp": 70,
                "gold": 0,
                "options": [
                    {"id": "strike", "name": "Strike", "kind": "card", "tags": [], "box": [250, 260, 430, 330]},
                    {"id": "skip", "name": "Skip", "kind": "skip", "tags": [], "box": [880, 930, 1040, 990]},
                ],
                "chosen": None,
                "skipped": False,
                "screenshot_path": "screen.png",
                "coordinate_space": "window_relative",
                "target_window": target_window.to_dict(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="current target window"):
        cli.main(
            [
                "act",
                "--snapshot",
                str(snapshot_path),
                "--choice",
                "pick:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
            ]
        )


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


def test_capture_screen_uses_pillow_bbox_without_real_screen(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def grab(*, bbox):
        calls.append(bbox)
        return Image.new("RGB", (5, 6), (4, 5, 6))

    monkeypatch.setattr(ImageGrab, "grab", grab)

    result = runtime.capture_screen(tmp_path / "screen.png", bbox=(1, 2, 6, 8))

    assert result == tmp_path / "screen.png"
    assert calls == [(1, 2, 6, 8)]


def test_capture_screen_passes_target_window_bbox_to_grabber(tmp_path: Path) -> None:
    calls = []

    def grabber(*, bbox):
        calls.append(bbox)
        return Image.new("RGB", (1280, 720), (4, 5, 6))

    result = runtime.capture_screen(tmp_path / "target.png", grabber=grabber, bbox=(100, 200, 1380, 920))

    assert result == tmp_path / "target.png"
    assert calls == [(100, 200, 1380, 920)]
    assert Image.open(result).size == (1280, 720)


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
