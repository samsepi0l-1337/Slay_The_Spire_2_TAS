import json
from pathlib import Path

from PIL import Image

from sts2_tas import cli


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


def _ack_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [
                    {"text": "타격", "box": [250, 260, 430, 330], "confidence": 0.99},
                    {"text": "수비", "box": [760, 260, 940, 330], "confidence": 0.99},
                    {"text": "강타", "box": [1270, 260, 1450, 330], "confidence": 0.99},
                    {"text": "넘기기", "box": [880, 930, 1040, 990], "confidence": 0.99},
                ],
                [{"text": "Single Player", "box": [780, 360, 1140, 430], "confidence": 0.99}],
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_cli_live_step_retries_until_polled_frame_acknowledges_change(tmp_path: Path, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-ocr-fixture-sequence",
            str(_ack_sequence(tmp_path / "ack-sequence.json")),
            "--ack-max-retries",
            "2",
            "--choice",
            "pick:strike",
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
    events = [json.loads(line) for line in input_log.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert len(events) == 2
    assert output["transition_ack"]["status"] == "changed"
    assert output["transition_ack"]["attempts"] == 2
    assert output["transition_ack"]["retry_count"] == 1
    assert [item["status"] for item in output["transition_ack"]["history"]] == ["no_op", "changed"]


def test_cli_live_step_retry_reports_timeout_when_polling_frame_is_missing(tmp_path: Path, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"
    sequence = tmp_path / "ack-sequence.json"
    sequence.write_text(
        json.dumps(
            [
                [
                    {"text": "타격", "box": [250, 260, 430, 330], "confidence": 0.99},
                    {"text": "수비", "box": [760, 260, 940, 330], "confidence": 0.99},
                    {"text": "강타", "box": [1270, 260, 1450, 330], "confidence": 0.99},
                    {"text": "넘기기", "box": [880, 930, 1040, 990], "confidence": 0.99},
                ]
            ]
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-ocr-fixture-sequence",
            str(sequence),
            "--ack-max-retries",
            "1",
            "--choice",
            "pick:strike",
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
    assert exit_code == 0
    assert output["transition_ack"]["status"] == "timeout"
    assert output["transition_ack"]["attempts"] == 2
    assert [item["status"] for item in output["transition_ack"]["history"]] == ["no_op", "timeout"]


def test_cli_live_step_can_retry_with_live_frame_polling(tmp_path: Path, monkeypatch, capsys) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    capture_calls = []

    class Provider:
        def __init__(self, *, language: str) -> None:
            assert language == "eng+kor"

        def recognize(self, image_path: Path):
            if "ack" in image_path.stem:
                return [cli.OcrToken(text="Single Player", box=(780, 360, 1140, 430), confidence=0.99)]
            return [
                cli.OcrToken(text="Strike", box=(250, 260, 430, 330), confidence=0.99),
                cli.OcrToken(text="Defend", box=(760, 260, 940, 330), confidence=0.99),
                cli.OcrToken(text="Bash", box=(1270, 260, 1450, 330), confidence=0.99),
                cli.OcrToken(text="Skip", box=(880, 930, 1040, 990), confidence=0.99),
            ]

    def fake_capture(path: Path, *, bbox=None):
        capture_calls.append((path, bbox))
        return _screen(path)

    class Detector:
        def detect(self, process: str):
            return TargetWindow(
                process=process,
                title="Main Window",
                bounds=WindowBounds(left=100, top=200, width=1280, height=720),
            )

    monkeypatch.setattr(cli, "TesseractOcrProvider", Provider)
    monkeypatch.setattr(cli, "capture_screen", fake_capture)
    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    exit_code = cli.main(
        [
            "live-step",
            "--screenshot-out",
            str(tmp_path / "live.png"),
            "--ocr-provider",
            "tesseract",
            "--ack-live-poll",
            "--target-process",
            "Slay the Spire 2",
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
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
    assert exit_code == 0
    assert [path for path, _bbox in capture_calls] == [tmp_path / "live.png", tmp_path / "live-ack-000001.png"]
    assert [bbox for _path, bbox in capture_calls] == [(100, 200, 1380, 920), (100, 200, 1380, 920)]
    assert output["transition_ack"]["status"] == "changed"
    assert output["transition_ack"]["attempts"] == 1


def test_cli_live_step_live_frame_polling_without_target_window(tmp_path: Path, monkeypatch, capsys) -> None:
    capture_calls = []

    class Provider:
        def __init__(self, *, language: str) -> None:
            pass

        def recognize(self, image_path: Path):
            if "ack" in image_path.stem:
                return [cli.OcrToken(text="Single Player", box=(780, 360, 1140, 430), confidence=0.99)]
            return [
                cli.OcrToken(text="Strike", box=(250, 260, 430, 330), confidence=0.99),
                cli.OcrToken(text="Defend", box=(760, 260, 940, 330), confidence=0.99),
                cli.OcrToken(text="Bash", box=(1270, 260, 1450, 330), confidence=0.99),
                cli.OcrToken(text="Skip", box=(880, 930, 1040, 990), confidence=0.99),
            ]

    def fake_capture(path: Path, *, bbox=None):
        capture_calls.append((path, bbox))
        return _screen(path)

    monkeypatch.setattr(cli, "TesseractOcrProvider", Provider)
    monkeypatch.setattr(cli, "capture_screen", fake_capture)

    exit_code = cli.main(
        [
            "live-step",
            "--screenshot-out",
            str(tmp_path / "live.png"),
            "--ocr-provider",
            "tesseract",
            "--ack-live-poll",
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
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
    assert exit_code == 0
    assert [bbox for _path, bbox in capture_calls] == [None, None]
    assert output["transition_ack"]["status"] == "changed"


def test_cli_live_step_live_poll_without_screenshot_output_times_out(tmp_path: Path, capsys) -> None:
    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-live-poll",
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
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
    assert exit_code == 0
    assert output["transition_ack"]["status"] == "timeout"
    assert output["transition_ack"]["attempts"] == 1
