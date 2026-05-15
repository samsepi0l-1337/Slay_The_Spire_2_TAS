import json
from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import cli
from sts2_tas import live_learning
from sts2_tas import recognition
from sts2_tas.schema import GameStep


def _screen(path: Path) -> Path:
    Image.new("RGB", (1920, 1080), (15, 18, 24)).save(path)
    return path


def _token(text: str, box: tuple[int, int, int, int]) -> dict[str, object]:
    return {"text": text, "box": list(box), "confidence": 0.99}


def _ocr_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [_token("Single Player", (780, 360, 1140, 430))],
                [_token("Standard", (790, 400, 1130, 470))],
                [_token("Ironclad", (240, 260, 500, 360))],
                [
                    _token("Strike", (250, 260, 430, 330)),
                    _token("Defend", (760, 260, 940, 330)),
                    _token("Bash", (1270, 260, 1450, 330)),
                    _token("Skip", (880, 930, 1040, 990)),
                ],
                [
                    _token("Victory!", (760, 160, 1160, 250)),
                    _token("New Run", (810, 780, 1110, 850)),
                ],
            ]
        ),
        encoding="utf-8",
    )
    return path


def _game_over_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [
                    _token("Game Over", (760, 160, 1160, 250)),
                    _token("New Run", (810, 780, 1110, 850)),
                ]
            ]
        ),
        encoding="utf-8",
    )
    return path


def _unknown_sequence(path: Path) -> Path:
    path.write_text(json.dumps([[_token("Loading", (820, 480, 1100, 540))]]), encoding="utf-8")
    return path


def _two_episode_training_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [
                    _token("Strike", (250, 260, 430, 330)),
                    _token("Defend", (760, 260, 940, 330)),
                    _token("Bash", (1270, 260, 1450, 330)),
                    _token("Skip", (880, 930, 1040, 990)),
                ],
                [
                    _token("Victory!", (760, 160, 1160, 250)),
                    _token("New Run", (810, 780, 1110, 850)),
                ],
                [
                    _token("Strike", (250, 260, 430, 330)),
                    _token("Defend", (760, 260, 940, 330)),
                    _token("Bash", (1270, 260, 1450, 330)),
                    _token("Skip", (880, 930, 1040, 990)),
                ],
                [
                    _token("Game Over", (760, 160, 1160, 250)),
                    _token("New Run", (810, 780, 1110, 850)),
                ],
            ]
        ),
        encoding="utf-8",
    )
    return path


def _duplicate_terminal_sequence(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                [
                    _token("Strike", (250, 260, 430, 330)),
                    _token("Defend", (760, 260, 940, 330)),
                    _token("Bash", (1270, 260, 1450, 330)),
                    _token("Skip", (880, 930, 1040, 990)),
                ],
                [
                    _token("Victory!", (760, 160, 1160, 250)),
                    _token("New Run", (810, 780, 1110, 850)),
                ],
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_parse_ocr_screen_maps_game_over_restart_action(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Game Over", (760, 160, 1160, 250), 0.99),
            recognition.OcrToken("New Run", (810, 780, 1110, 850), 0.99),
        ]
    )

    parsed = recognition.parse_ocr_screen(_screen(tmp_path / "game-over.png"), provider)

    assert parsed.kind == "game_over"
    assert [(option.id, option.kind) for option in parsed.options] == [("new_run", "restart_run")]


def test_parse_ocr_screen_maps_compact_singleplayer_menu_text(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Singleplayer", (780, 360, 1140, 430), 0.99),
        ]
    )

    parsed = recognition.parse_ocr_screen(_screen(tmp_path / "main-menu.png"), provider)

    assert parsed.kind == "main_menu"
    assert [(option.id, option.kind) for option in parsed.options] == [
        ("single_player", "select_single_player")
    ]


def test_parse_ocr_screen_maps_the_ironclad_character_title(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("The Ironclad", (3, 352, 501, 447), 0.96),
        ]
    )

    parsed = recognition.parse_ocr_screen(_screen(tmp_path / "character-select.png"), provider)

    assert parsed.kind == "character_select"
    assert [(option.id, option.kind) for option in parsed.options] == [("ironclad", "select_character")]


def test_parse_ocr_screen_maps_right_side_loot_skip(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Loot!", (910, 247, 1014, 286), 0.96),
            recognition.OcrToken("Skip", (1685, 809, 1755, 843), 0.96),
        ]
    )

    parsed = recognition.parse_ocr_screen(_screen(tmp_path / "loot.png"), provider)

    assert parsed.kind == "card_reward"
    assert [(option.id, option.kind) for option in parsed.options] == [("skip", "skip")]


def test_parse_ocr_screen_uses_visual_right_side_skip_when_ocr_misses_text(tmp_path: Path) -> None:
    screen = _screen(tmp_path / "visual-skip.png")
    image = Image.open(screen)
    for x in range(1580, 1860):
        for y in range(760, 875):
            image.putpixel((x, y), (165, 35, 28))
    image.save(screen)
    provider = recognition.FakeOcrProvider([])

    parsed = recognition.parse_ocr_screen(screen, provider)

    assert parsed.kind == "card_reward"
    assert [(option.id, option.kind) for option in parsed.options] == [("skip", "skip")]


def test_parse_ocr_screen_fails_closed_on_low_confidence_catalog_tokens(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Strike", (250, 260, 430, 330), 0.99),
            recognition.OcrToken("Defend", (760, 260, 940, 330), 0.30),
            recognition.OcrToken("Bash", (1270, 260, 1450, 330), 0.99),
            recognition.OcrToken("Skip", (880, 930, 1040, 990), 0.99),
        ]
    )

    with pytest.raises(ValueError, match="unknown OCR screen layout"):
        recognition.parse_ocr_screen(_screen(tmp_path / "reward.png"), provider)


def test_live_learn_loop_handles_game_over_restart_without_episode_output(tmp_path: Path, capsys) -> None:
    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_game_over_sequence(tmp_path / "game-over-sequence.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--choice",
            "pick:strike",
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
            "9",
            "--hp",
            "0",
            "--gold",
            "0",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["steps"] == 1
    assert not (tmp_path / "dataset.jsonl").exists()
    assert not (tmp_path / "inputs.jsonl").exists()


def test_ocr_fixture_sequence_rejects_empty_payload(tmp_path: Path) -> None:
    path = tmp_path / "empty-sequence.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one frame"):
        live_learning._ocr_sequence_tokens(path, 1)


def test_default_action_requires_legal_candidate() -> None:
    class Step:
        actions = []

    with pytest.raises(ValueError, match="no legal action"):
        live_learning._default_action_id(Step())  # type: ignore[arg-type]


def test_live_learn_loop_stop_file_exits_before_next_iteration(tmp_path: Path, capsys) -> None:
    stop_file = tmp_path / "stop-live-loop.flag"
    stop_file.write_text("stop", encoding="utf-8")

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_ocr_sequence(tmp_path / "ocr-sequence.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--policy",
            "first-legal",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--stop-file",
            str(stop_file),
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
    assert output == {
        "steps": 0,
        "trained": 0,
        "interrupted": True,
        "dataset": str(tmp_path / "dataset.jsonl"),
        "model": None,
    }
    assert not (tmp_path / "dataset.jsonl").exists()
    assert not (tmp_path / "inputs.jsonl").exists()


def test_live_learn_loop_first_legal_policy_can_replay_full_session(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "dataset.jsonl"
    episodes = tmp_path / "episodes.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_ocr_sequence(tmp_path / "ocr-sequence.json")),
            "--dataset",
            str(dataset),
            "--episodes-out",
            str(episodes),
            "--policy",
            "first-legal",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--max-steps",
            "5",
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
    steps = [GameStep.from_json(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    episode_rows = [json.loads(line) for line in episodes.read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert output["steps"] == 5
    assert [step.label_source for step in steps] == ["heuristic"]
    assert [step.chosen_action_id for step in steps] == ["pick_card|option=strike"]
    assert episode_rows[0]["restart_action_id"] == "restart_run|option=new_run"


def test_live_learn_loop_records_unknown_screen_and_continues_when_failure_log_exists(
    tmp_path: Path, capsys
) -> None:
    failure_log = tmp_path / "failures.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_unknown_sequence(tmp_path / "unknown-sequence.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--policy",
            "first-legal",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
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

    output = json.loads(capsys.readouterr().out)
    failure = json.loads(failure_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert output["steps"] == 1
    assert failure["reason"] == "screen_parse_failed"
    assert "unknown OCR screen layout" in failure["controller_error"]
    assert not (tmp_path / "dataset.jsonl").exists()


def test_live_learn_loop_restarts_after_terminal_without_training_menu_rows(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "dataset.jsonl"
    episodes = tmp_path / "episodes.jsonl"
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_ocr_sequence(tmp_path / "ocr-sequence.json")),
            "--dataset",
            str(dataset),
            "--episodes-out",
            str(episodes),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--max-steps",
            "5",
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
    steps = [GameStep.from_json(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    episode_rows = [json.loads(line) for line in episodes.read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert output["steps"] == 5
    assert output["trained"] == 0
    assert not input_log.exists()
    assert [step.state.decision_context for step in steps] == ["card_reward"]
    assert steps[0].chosen_action_id == "pick_card|option=strike"
    assert episode_rows == [
        {
            "episode": 1,
            "floor_reached": 1,
            "hp_remaining": 70,
            "restart_action_id": "restart_run|option=new_run",
            "steps": 1,
            "victory": True,
        }
    ]
    assert steps[0].outcome is not None
    assert steps[0].outcome.victory is True
    assert steps[0].outcome.immediate_reward == 1.0
    assert steps[0].outcome.terminal is False


def test_live_learn_loop_does_not_duplicate_terminal_episode_rows(tmp_path: Path, capsys) -> None:
    episodes = tmp_path / "episodes.jsonl"

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_duplicate_terminal_sequence(tmp_path / "ocr-sequence.json")),
            "--dataset",
            str(tmp_path / "dataset.jsonl"),
            "--episodes-out",
            str(episodes),
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--max-steps",
            "3",
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

    episode_rows = [json.loads(line) for line in episodes.read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert len(episode_rows) == 1
    assert episode_rows[0]["steps"] == 1


def test_episode_steps_are_independent_from_train_interval_resets(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "dataset.jsonl"
    episodes = tmp_path / "episodes.jsonl"
    train_rewards = []
    trained_models = []

    def fake_train(steps, *args, **kwargs):
        train_rewards.append([None if step.outcome is None else step.outcome.immediate_reward for step in steps])
        return object()

    monkeypatch.setattr(live_learning, "train_torch_model", fake_train)
    monkeypatch.setattr(live_learning, "save_model", lambda model, path: trained_models.append(path))

    exit_code = cli.main(
        [
            "live-learn-loop",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture-sequence",
            str(_two_episode_training_sequence(tmp_path / "ocr-sequence.json")),
            "--dataset",
            str(dataset),
            "--episodes-out",
            str(episodes),
            "--choice",
            "pick:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--max-steps",
            "4",
            "--train-every",
            "1",
            "--model-out",
            str(tmp_path / "model.pt"),
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
    episode_rows = [json.loads(line) for line in episodes.read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert output["trained"] == 4
    assert len(trained_models) == 4
    assert train_rewards[-1] == [1.0, 0.0]
    assert [row["steps"] for row in episode_rows] == [1, 1]
