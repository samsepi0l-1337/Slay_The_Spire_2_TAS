import json
from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import cli
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState, TargetWindow, WindowBounds
from sts2_tas.trajectory import TrajectoryStep
from sts2_tas.live_learning import _trajectory_reward


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


def _combat_ocr_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {"text": "HP 70/80", "box": [80, 930, 220, 980], "confidence": 0.99},
                {"text": "Energy 3/3", "box": [420, 910, 540, 970], "confidence": 0.99},
                {"text": "Block 0", "box": [230, 910, 330, 970], "confidence": 0.99},
                {"text": "Turn 1", "box": [550, 910, 650, 970], "confidence": 0.99},
                {"text": "Hand Strike cost 1 attack", "box": [250, 820, 430, 1010], "confidence": 0.99},
                {
                    "text": "Monster Jaw Worm 30/44 block 3 attack 7x1",
                    "box": [1270, 260, 1560, 570],
                    "confidence": 0.99,
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


def _changed_ack_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
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
                ]
            ]
        ),
        encoding="utf-8",
    )
    return path


def _low_confidence_combat_ocr_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {"text": "HP 70/80", "box": [80, 930, 220, 980], "confidence": 0.50},
                {"text": "Energy 3/3", "box": [420, 910, 540, 970], "confidence": 0.99},
                {"text": "Block 0", "box": [230, 910, 330, 970], "confidence": 0.99},
                {"text": "Turn 1", "box": [550, 910, 650, 970], "confidence": 0.99},
                {"text": "Hand Strike cost 1 attack", "box": [250, 820, 430, 1010], "confidence": 0.99},
                {
                    "text": "Monster Jaw Worm 30/44 block 3 attack 7x1",
                    "box": [1270, 260, 1560, 570],
                    "confidence": 0.99,
                },
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


def _minimal_game_step(outcome: StepOutcome) -> GameStep:
    action = ActionCandidate(action_type="end_turn")
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="combat",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=[action],
        chosen_action_id=action.identity,
        outcome=outcome,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )


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


def test_live_learn_loop_treats_combat_choice_as_gameplay_label(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "dataset.jsonl"
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "combat.png")),
            "--ocr-fixture",
            str(_combat_ocr_fixture(tmp_path / "combat-ocr.json")),
            "--dataset",
            str(dataset),
            "--choice",
            "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
            "--input-log",
            str(input_log),
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
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

    output = json.loads(capsys.readouterr().out)
    step = _load_steps(dataset)[0]
    event = json.loads(input_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert output["steps"] == 1
    assert step.state.decision_context == "combat"
    assert step.chosen_action_id == "play_card|source_card=hand-0-strike|target_monster=jaw_worm:0"
    assert event["input_plan"] == {
        "kind": "sequence",
        "steps": [
            {"kind": "click", "x": 340, "y": 915},
            {"kind": "click", "x": 1415, "y": 415},
        ],
    }


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
        def __init__(
            self,
            *,
            language: str,
            binary: str = "tesseract",
            tessdata_dir: Path | None = None,
            page_segmentation_mode: int | None = None,
        ) -> None:
            assert language == "eng+kor"
            assert binary == "tesseract"
            assert tessdata_dir is None
            assert page_segmentation_mode is None

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
            "--allow-model-self-labels",
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


def test_live_learn_loop_does_not_self_label_model_choices_by_default(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    class Result:
        best = type("Best", (), {"action_id": "skip_reward|option=skip"})()

    monkeypatch.setattr(live_learning, "load_model", lambda path: object())
    monkeypatch.setattr(live_learning, "recommend", lambda model, step: Result())

    dataset = tmp_path / "dataset.jsonl"
    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--model",
            str(tmp_path / "model.pt"),
            "--dataset",
            str(dataset),
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
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

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert output["trained"] == 0
    assert not dataset.exists()


def test_live_learn_loop_execute_native_uses_injected_controller(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    sent = []

    class Controller:
        def send(self, action) -> None:
            sent.append(action.to_event())

    monkeypatch.setattr(live_learning, "NativeInputController", Controller)

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--input-backend",
            "native",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
        ]
    )

    assert exit_code == 0
    assert sent[0]["input_plan"] == {"kind": "click", "x": 340, "y": 295}


def test_live_learn_loop_does_not_label_failed_execute_action(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("input failed")

    monkeypatch.setattr(live_learning, "NativeInputController", Controller)

    with pytest.raises(RuntimeError, match="input failed"):
        cli.main(
            [
                *_base_args(tmp_path),
                "--max-steps",
                "1",
                "--input-backend",
                "native",
                "--execute",
                "--ack-ocr-fixture-sequence",
                str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
            ]
        )

    assert not (tmp_path / "dataset.jsonl").exists()


def test_live_learn_loop_execute_jsonl_writes_input_event(tmp_path: Path) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
        ]
    )

    event = json.loads(input_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert event["input_plan"] == {"kind": "click", "x": 340, "y": 295}
    assert (tmp_path / "dataset.jsonl").exists()


def test_live_learn_loop_logs_missing_ack_without_dataset_append(tmp_path: Path, capsys) -> None:
    failure_log = tmp_path / "failures.jsonl"
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "1", "--execute", "--failure-log", str(failure_log)])

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not input_log.exists()
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "missing_transition_ack"
    assert failure["action_id"] == "pick_card|option=strike"
    assert failure["after_signature"] is None


def test_live_learn_loop_missing_ack_without_failure_log_raises_before_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires transition ack"):
        cli.main([*_base_args(tmp_path), "--max-steps", "1", "--execute"])

    assert not (tmp_path / "inputs.jsonl").exists()
    assert not (tmp_path / "dataset.jsonl").exists()


def test_live_learn_loop_logs_fail_closed_perception_without_input(tmp_path: Path, capsys) -> None:
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_low_confidence_combat_ocr_fixture(tmp_path / "low-confidence.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--choice",
            "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--failure-log",
            str(failure_log),
            "--execute",
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

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "inputs.jsonl").exists()
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "fail_closed_perception"


def test_live_learn_loop_raises_fail_closed_perception_without_failure_log(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="perception quality"):
        cli.main(
            [
                "live-learn-loop",
                "--capture-fixture",
                str(_screen(tmp_path / "screen.png")),
                "--ocr-fixture",
                str(_low_confidence_combat_ocr_fixture(tmp_path / "low-confidence.json")),
                "--dataset",
                str(tmp_path / "dataset.jsonl"),
                "--choice",
                "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
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


def test_live_learn_loop_logs_ack_controller_error_without_append(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("ack input failed")

    monkeypatch.setattr(live_learning, "JsonlInputController", lambda path: Controller())
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
            "--failure-log",
            str(failure_log),
        ]
    )

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "controller_error"
    assert failure["controller_error"] == "ack input failed"


def test_live_learn_loop_raises_ack_controller_error_without_failure_log(tmp_path: Path, monkeypatch) -> None:
    import sts2_tas.live_learning as live_learning

    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("ack input failed")

    monkeypatch.setattr(live_learning, "JsonlInputController", lambda path: Controller())

    with pytest.raises(RuntimeError, match="ack input failed"):
        cli.main(
            [
                *_base_args(tmp_path),
                "--max-steps",
                "1",
                "--execute",
                "--ack-ocr-fixture-sequence",
                str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
            ]
        )


def test_live_learn_loop_logs_no_ack_controller_error_without_raise(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    class Controller:
        def send(self, action) -> None:
            raise RuntimeError("missing ack input failed")

    monkeypatch.setattr(live_learning, "JsonlInputController", lambda path: Controller())
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "1", "--execute", "--failure-log", str(failure_log)])

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert not (tmp_path / "inputs.jsonl").exists()
    assert failure["reason"] == "missing_transition_ack"
    assert "controller_error" not in failure


def test_live_learn_loop_live_ack_poll_uses_target_window_capture_and_blocks_no_op(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import sts2_tas.live_learning as live_learning

    capture_calls = []

    class Detector:
        def detect(self, process: str):
            return TargetWindow(process=process, title="Main Window", bounds=WindowBounds(100, 200, 1280, 720))

    def fake_capture(path: Path, *, bbox=None):
        capture_calls.append((path, bbox))
        return _screen(path)

    monkeypatch.setattr(live_learning, "WindowDetector", lambda: Detector())
    monkeypatch.setattr(live_learning, "capture_screen", fake_capture)
    failure_log = tmp_path / "failures.jsonl"

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
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--execute",
            "--ack-live-poll",
            "--target-process",
            "Slay the Spire 2",
            "--failure-log",
            str(failure_log),
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

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "no_op"
    assert capture_calls == [
        (tmp_path / "live-000001.png", (100, 200, 1380, 920)),
        (tmp_path / "live-ack-000001.png", (100, 200, 1380, 920)),
    ]


def test_live_learn_loop_live_ack_poll_without_target_window_blocks_no_op(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import sts2_tas.live_learning as live_learning

    capture_calls = []

    def fake_capture(path: Path, *, bbox=None):
        capture_calls.append((path, bbox))
        return _screen(path)

    monkeypatch.setattr(live_learning, "capture_screen", fake_capture)
    failure_log = tmp_path / "failures.jsonl"

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
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--execute",
            "--ack-live-poll",
            "--failure-log",
            str(failure_log),
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

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "no_op"
    assert capture_calls == [
        (tmp_path / "live-000001.png", None),
        (tmp_path / "live-ack-000001.png", None),
    ]


def test_live_learn_loop_live_ack_poll_requires_screenshot_out_for_ack_frame(tmp_path: Path, capsys) -> None:
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main([*_base_args(tmp_path), "--max-steps", "1", "--execute", "--ack-live-poll", "--failure-log", str(failure_log)])

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "timeout"


def test_live_learn_loop_empty_ack_sequence_times_out_without_append(tmp_path: Path, capsys) -> None:
    ack_sequence = tmp_path / "ack-sequence.json"
    ack_sequence.write_text("[]", encoding="utf-8")
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(ack_sequence),
            "--failure-log",
            str(failure_log),
        ]
    )

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert failure["reason"] == "timeout"


def test_live_learn_loop_preflight_failure_raises_without_failure_log(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(OSError):
        cli.main([*_base_args(tmp_path), "--dataset", str(blocked_parent / "dataset.jsonl"), "--max-steps", "1"])


def test_live_learn_loop_rejects_negative_ack_retries(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ack-max-retries"):
        cli.main([*_base_args(tmp_path), "--max-steps", "1", "--ack-max-retries", "-1"])


def test_live_step_raises_fail_closed_perception_without_failure_log(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="perception quality"):
        cli.main(
            [
                "live-step",
                "--capture-fixture",
                str(_screen(tmp_path / "screen.png")),
                "--ocr-fixture",
                str(_low_confidence_combat_ocr_fixture(tmp_path / "low-confidence.json")),
                "--choice",
                "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
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


def test_live_learn_loop_appends_dataset_and_trajectory_only_after_changed_ack(tmp_path: Path, capsys) -> None:
    trajectory_out = tmp_path / "trajectory.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_changed_ack_sequence(tmp_path / "ack-sequence.json")),
            "--trajectory-out",
            str(trajectory_out),
            "--failure-log",
            str(tmp_path / "failures.jsonl"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    steps = _load_steps(tmp_path / "dataset.jsonl")
    trajectory = [TrajectoryStep.from_json(line) for line in trajectory_out.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert output["steps"] == 1
    assert [step.chosen_action_id for step in steps] == ["pick_card|option=strike"]
    assert len(trajectory) == 1
    assert trajectory[0].selected_action.identity == "pick_card|option=strike"
    assert trajectory[0].state_before.room_type == "card_reward"
    assert trajectory[0].state_after.room_type == "main_menu"


def test_trajectory_reward_maps_terminal_outcomes() -> None:
    win = _minimal_game_step(StepOutcome(True, 1, 70, immediate_reward=0.0, terminal=True))
    loss = _minimal_game_step(StepOutcome(False, 1, 0, immediate_reward=0.0, terminal=True))
    reward = _minimal_game_step(StepOutcome(False, 1, 10, immediate_reward=0.25, terminal=False))

    assert _trajectory_reward(win) == 1.0
    assert _trajectory_reward(loss) == -1.0
    assert _trajectory_reward(reward) == 0.25


def test_live_learn_loop_blocks_dataset_and_trajectory_append_when_ack_does_not_change(tmp_path: Path, capsys) -> None:
    failure_log = tmp_path / "failures.jsonl"
    trajectory_out = tmp_path / "trajectory.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--max-steps",
            "1",
            "--execute",
            "--ack-ocr-fixture-sequence",
            str(_unchanged_ack_sequence(tmp_path / "ack-sequence.json")),
            "--ack-max-retries",
            "0",
            "--trajectory-out",
            str(trajectory_out),
            "--failure-log",
            str(failure_log),
        ]
    )

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert not trajectory_out.exists()
    assert not (tmp_path / "inputs.jsonl").exists()
    assert failure["reason"] == "no_op"
    assert failure["action_id"] == "pick_card|option=strike"
    assert failure["before_signature"] == failure["after_signature"]
    assert failure["retry_count"] == 0
    assert failure["latency_ms"] >= 0


def test_live_learn_loop_preflights_dataset_before_controller_input(tmp_path: Path, monkeypatch, capsys) -> None:
    import sts2_tas.live_learning as live_learning

    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    sent = []

    class Controller:
        def send(self, action) -> None:
            sent.append(action.to_event())

    monkeypatch.setattr(live_learning, "JsonlInputController", lambda path: Controller())
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--dataset",
            str(blocked_parent / "dataset.jsonl"),
            "--max-steps",
            "1",
            "--execute",
            "--failure-log",
            str(failure_log),
        ]
    )

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert sent == []
    assert failure["reason"] == "dataset_preflight_failed"
    assert failure["action_id"] == "pick_card|option=strike"


def test_live_learn_loop_preflights_dataset_file_path_before_controller_input(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import sts2_tas.live_learning as live_learning

    dataset_dir = tmp_path / "dataset.jsonl"
    dataset_dir.mkdir()
    sent = []

    class Controller:
        def send(self, action) -> None:
            sent.append(action.to_event())

    monkeypatch.setattr(live_learning, "JsonlInputController", lambda path: Controller())
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            *_base_args(tmp_path),
            "--dataset",
            str(dataset_dir),
            "--max-steps",
            "1",
            "--execute",
            "--failure-log",
            str(failure_log),
        ]
    )

    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert sent == []
    assert failure["reason"] == "dataset_preflight_failed"
    assert failure["action_id"] == "pick_card|option=strike"
    assert "directory" in failure["controller_error"]


def test_live_step_logs_fail_closed_perception_without_input(tmp_path: Path) -> None:
    failure_log = tmp_path / "failures.jsonl"
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "live-step",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_low_confidence_combat_ocr_fixture(tmp_path / "low-confidence.json")),
            "--choice",
            "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
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
    assert failure["reason"] == "fail_closed_perception"
    assert "perception quality below threshold" in failure["controller_error"]
