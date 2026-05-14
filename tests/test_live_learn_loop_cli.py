import json
from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import cli
from sts2_tas.schema import ActionCandidate, GameStep, TargetWindow, WindowBounds


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


def _base_args(tmp_path: Path) -> list[str]:
    return [
        "live-learn-loop",
        "--capture-fixture",
        str(_screen(tmp_path / "screen.png")),
        "--ocr-fixture",
        str(_ocr_fixture(tmp_path / "ocr.json")),
        "--dataset",
        str(tmp_path / "dataset.jsonl"),
        "--choice",
        "pick:strike",
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


def _load_steps(path: Path) -> list[GameStep]:
    return [GameStep.from_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_live_learn_loop_appends_labeled_steps_without_input_by_default(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "dataset.jsonl"
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "2"])

    output = json.loads(capsys.readouterr().out)
    steps = _load_steps(dataset)
    assert exit_code == 0
    assert output == {
        "steps": 2,
        "trained": 0,
        "interrupted": False,
        "dataset": str(dataset),
        "model": None,
    }
    assert [step.chosen_action_id for step in steps] == ["pick_card|option=strike", "pick_card|option=strike"]
    assert [step.screenshot_path for step in steps] == [tmp_path / "screen.png", tmp_path / "screen.png"]
    assert not input_log.exists()


def test_live_learn_loop_rejects_native_backend_without_execute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="native input backend requires --execute"):
        cli.main([*_base_args(tmp_path), "--max-steps", "1", "--input-backend", "native"])


def test_live_learn_loop_trains_after_new_labeled_step_interval(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    train_calls = []
    saved = []

    def fake_train(steps, character: str, *, epochs: int, batch_size: int, device: str):
        train_calls.append(
            {
                "chosen": [step.chosen_action_id for step in steps],
                "character": character,
                "epochs": epochs,
                "batch_size": batch_size,
                "device": device,
            }
        )
        return object()

    monkeypatch.setattr(live_learning, "train_torch_model", fake_train)
    monkeypatch.setattr(live_learning, "save_model", lambda model, path: saved.append(path))

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "3",
            "--train-every",
            "2",
            "--model-out",
            str(tmp_path / "model.pt"),
            "--epochs",
            "4",
            "--batch-size",
            "8",
            "--device",
            "cpu",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["trained"] == 1
    assert len(train_calls) == 1
    assert train_calls[0] == {
        "chosen": ["pick_card|option=strike", "pick_card|option=strike"],
        "character": "ironclad",
        "epochs": 4,
        "batch_size": 8,
        "device": "cpu",
    }
    assert saved == [tmp_path / "model.pt"]


def test_live_learn_loop_prints_summary_on_keyboard_interrupt(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    real_iteration = live_learning._run_live_learn_iteration
    calls = 0

    def interrupt_after_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return real_iteration(*args, **kwargs)

    monkeypatch.setattr(live_learning, "_run_live_learn_iteration", interrupt_after_first)

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "3"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output == {
        "steps": 1,
        "trained": 0,
        "interrupted": True,
        "dataset": str(tmp_path / "dataset.jsonl"),
        "model": None,
    }


def test_live_learn_loop_rejects_non_positive_train_interval(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="train-every"):
        cli.main([*_base_args(tmp_path), "--max-steps", "1", "--train-every", "0"])


def test_live_learn_loop_captures_numbered_screenshot_files(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    capture_calls = []

    def fake_capture(path: Path):
        capture_calls.append(path)
        return _screen(path)

    monkeypatch.setattr(live_learning, "capture_screen", fake_capture)

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--screenshot-out",
            str(tmp_path / "live.png"),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--choice",
            "skip",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--max-steps",
            "2",
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

    steps = _load_steps(tmp_path / "dataset.jsonl")
    assert exit_code == 0
    assert capture_calls == [tmp_path / "live-000001.png", tmp_path / "live-000002.png"]
    assert [step.screenshot_path for step in steps] == capture_calls


def test_live_learn_loop_can_use_model_tesseract_and_target_window_capture(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    capture_calls = []

    class Provider:
        def __init__(self, *, language: str) -> None:
            assert language == "eng+kor"

        def recognize(self, image_path: Path):
            return [
                live_learning.OcrToken(text="Strike", box=(250, 260, 430, 330), confidence=0.99),
                live_learning.OcrToken(text="Defend", box=(760, 260, 940, 330), confidence=0.99),
                live_learning.OcrToken(text="Bash", box=(1270, 260, 1450, 330), confidence=0.99),
                live_learning.OcrToken(text="Skip", box=(880, 930, 1040, 990), confidence=0.99),
            ]

    class Detector:
        def detect(self, process: str):
            return TargetWindow(
                process=process,
                title="Main Window",
                bounds=WindowBounds(left=100, top=200, width=1280, height=720),
            )

    class Result:
        best = type("Best", (), {"action_id": "skip_reward|option=skip"})()

    def fake_capture(path: Path, *, bbox):
        capture_calls.append((path, bbox))
        return _screen(path)

    monkeypatch.setattr(live_learning, "TesseractOcrProvider", Provider)
    monkeypatch.setattr(live_learning, "WindowDetector", lambda: Detector())
    monkeypatch.setattr(live_learning, "capture_screen", fake_capture)
    monkeypatch.setattr(live_learning, "load_model", lambda path: object())
    monkeypatch.setattr(live_learning, "recommend", lambda model, step: Result())

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--screenshot-out",
            str(tmp_path / "target.png"),
            "--ocr-provider",
            "tesseract",
            "--model",
            str(tmp_path / "model.pt"),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--target-process",
            "Slay the Spire 2",
            "--max-steps",
            "1",
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

    step = _load_steps(tmp_path / "dataset.jsonl")[0]
    assert exit_code == 0
    assert capture_calls == [(tmp_path / "target-000001.png", (100, 200, 1380, 920))]
    assert step.chosen_action_id == "skip_reward|option=skip"


def test_live_learn_loop_execute_native_uses_injected_controller(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    sent = []

    class Controller:
        def send(self, action) -> None:
            sent.append(action.to_event())

    monkeypatch.setattr(live_learning, "NativeInputController", Controller)

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "1", "--input-backend", "native", "--execute"])

    assert exit_code == 0
    assert sent[0]["input_plan"] == {"kind": "click", "x": 340, "y": 295}


def test_live_learn_loop_does_not_label_failed_execute_action(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("input failed")

    monkeypatch.setattr(live_learning, "NativeInputController", Controller)

    with pytest.raises(RuntimeError, match="input failed"):
        cli.main([*_base_args(tmp_path), "--max-steps", "1", "--input-backend", "native", "--execute"])

    assert not (tmp_path / "dataset.jsonl").exists()


def test_live_learn_loop_execute_jsonl_writes_input_event(tmp_path: Path) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "1", "--execute"])

    event = json.loads(input_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert event["input_plan"] == {"kind": "click", "x": 340, "y": 295}


def test_live_learn_loop_requires_fixture_for_fixture_ocr(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    del args[args.index("--ocr-fixture") : args.index("--ocr-fixture") + 2]

    with pytest.raises(ValueError, match="ocr fixture"):
        cli.main([*args, "--max-steps", "1"])


def test_live_learn_loop_rewrites_missing_choice_error(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    args[args.index("pick:strike")] = "pick:missing"

    with pytest.raises(ValueError, match="chosen action is not present"):
        cli.main([*args, "--max-steps", "1"])


def test_live_learn_loop_preserves_non_presence_choice_errors(tmp_path: Path) -> None:
    import sts2_tas.live_learning as live_learning

    cli.main([*_base_args(tmp_path), "--max-steps", "1"])
    step = _load_steps(tmp_path / "dataset.jsonl")[0]
    illegal_step = GameStep(
        state=step.state,
        actions=[
            ActionCandidate(action_type="pick_card", option_id="strike", screen_box=(250, 260, 430, 330), legal=False),
            ActionCandidate(action_type="skip_reward", option_id="skip", screen_box=(880, 930, 1040, 990), legal=True),
        ],
        chosen_action_id=None,
        outcome=step.outcome,
        observation=step.observation,
        screenshot_path=step.screenshot_path,
    )

    with pytest.raises(ValueError, match="not legal"):
        live_learning._resolve_action_id(illegal_step, "pick:strike")
