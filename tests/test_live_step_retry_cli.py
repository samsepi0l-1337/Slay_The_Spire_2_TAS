import json
from pathlib import Path

from PIL import Image
import pytest

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


def _unchanged_ack_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [
                    {"text": "타격", "box": [250, 260, 430, 330], "confidence": 0.99},
                    {"text": "수비", "box": [760, 260, 940, 330], "confidence": 0.99},
                    {"text": "강타", "box": [1270, 260, 1450, 330], "confidence": 0.99},
                    {"text": "넘기기", "box": [880, 930, 1040, 990], "confidence": 0.99},
                ],
            ]
        ),
        encoding="utf-8",
    )
    return path


def _empty_ack_sequence(path: Path) -> Path:
    path.write_text("[]", encoding="utf-8")
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
    assert len(events) == 1
    assert output["transition_ack"]["status"] == "changed"
    assert output["transition_ack"]["attempts"] == 2
    assert output["transition_ack"]["retry_count"] == 1
    assert [item["status"] for item in output["transition_ack"]["history"]] == ["no_op", "changed"]


def test_cli_live_step_rejects_negative_ack_retry_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ack-max-retries"):
        cli.main(
            [
                "live-step",
                "--capture-fixture",
                str(_screen(tmp_path / "screen.png")),
                "--ocr-fixture",
                str(_ocr_fixture(tmp_path / "ocr.json")),
                "--ack-ocr-fixture-sequence",
                str(_ack_sequence(tmp_path / "ack-sequence.json")),
                "--ack-max-retries",
                "-1",
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


@pytest.mark.parametrize(
    ("sequence_name", "sequence_factory", "ack_max_retries", "expected_reason"),
    [
        ("unchanged", _unchanged_ack_sequence, "0", "no_op"),
        ("missing", _empty_ack_sequence, "0", "timeout"),
    ],
)
def test_cli_live_step_failure_log_records_ack_failures_without_raise(
    tmp_path: Path,
    capsys,
    sequence_name: str,
    sequence_factory,
    ack_max_retries: str,
    expected_reason: str,
) -> None:
    failure_log = tmp_path / f"{sequence_name}-failures.jsonl"
    input_log = tmp_path / f"{sequence_name}-inputs.jsonl"

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / f"{sequence_name}-screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / f"{sequence_name}-ocr.json")),
            "--ack-ocr-fixture-sequence",
            str(sequence_factory(tmp_path / f"{sequence_name}-ack-sequence.json")),
            "--ack-max-retries",
            ack_max_retries,
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--failure-log",
            str(failure_log),
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
    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert output["transition_ack"]["status"] == expected_reason
    assert failure["reason"] == expected_reason
    assert failure["action_id"] == "pick_card|option=strike"
    assert failure["before_signature"]
    if expected_reason == "no_op":
        assert failure["after_signature"] == failure["before_signature"]
    else:
        assert failure["after_signature"] is None
    assert failure["retry_count"] == 0
    assert failure["latency_ms"] >= 0
    assert not input_log.exists()


def test_cli_live_step_failure_log_records_controller_error_without_raise(tmp_path: Path, monkeypatch, capsys) -> None:
    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("controller failed")

    monkeypatch.setattr(cli, "JsonlInputController", lambda path: Controller())
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-ocr-fixture-sequence",
            str(_ack_sequence(tmp_path / "ack-sequence.json")),
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--failure-log",
            str(failure_log),
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
    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert output["action"]["controller_error"] == "controller failed"
    assert failure["reason"] == "controller_error"
    assert failure["action_id"] == "pick_card|option=strike"
    assert failure["before_signature"]
    assert failure["after_signature"] is None
    assert failure["retry_count"] == 0
    assert failure["latency_ms"] >= 0
    assert failure["controller_error"] == "controller failed"


def test_cli_live_step_rolls_back_input_log_when_single_ack_fixture_fails(tmp_path: Path, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"
    failure_log = tmp_path / "failures.jsonl"
    bad_ack_fixture = tmp_path / "bad-ack.json"
    bad_ack_fixture.write_text("{", encoding="utf-8")

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-ocr-fixture",
            str(bad_ack_fixture),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--failure-log",
            str(failure_log),
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

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert not input_log.exists()
    assert failure["reason"] == "controller_error"
    assert "Expecting property name" in failure["controller_error"]


def test_cli_live_step_rolls_back_input_log_when_ack_poll_raises(tmp_path: Path, monkeypatch, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"
    failure_log = tmp_path / "failures.jsonl"

    def fail_ack_poll(*args, **kwargs):
        raise RuntimeError("ack poll failed")

    monkeypatch.setattr(cli, "_ack_poll_step", fail_ack_poll)

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--ack-ocr-fixture-sequence",
            str(_ack_sequence(tmp_path / "ack-sequence.json")),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--failure-log",
            str(failure_log),
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

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert not input_log.exists()
    assert failure["reason"] == "controller_error"
    assert failure["controller_error"] == "ack poll failed"


def test_cli_live_step_controller_error_without_failure_log_raises(tmp_path: Path, monkeypatch) -> None:
    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("controller failed")

    monkeypatch.setattr(cli, "JsonlInputController", lambda path: Controller())

    with pytest.raises(RuntimeError, match="controller failed"):
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
    assert not (tmp_path / "inputs.jsonl").exists()
