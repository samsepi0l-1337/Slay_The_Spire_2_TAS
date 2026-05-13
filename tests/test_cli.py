import json
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from sts2_tas import cli
from sts2_tas.schema import (
    ActionCandidate,
    GameStep,
    ObservationQuality,
    PlayerState,
    StepOutcome,
    StructuredGameState,
)


def _reward_image(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), (15, 18, 24))
    draw = ImageDraw.Draw(image)
    for left in (120, 350, 580):
        draw.rectangle((left, 120, left + 150, 360), fill=(48, 90, 170))
    draw.rectangle((380, 500, 520, 550), fill=(88, 88, 88))
    image.save(path)
    return path


def _relic_image(path: Path, count: int = 3) -> Path:
    image = Image.new("RGB", (900, 600), (15, 18, 24))
    draw = ImageDraw.Draw(image)
    for left in (260, 420, 580)[:count]:
        draw.rectangle((left, 220, left + 80, 300), fill=(185, 142, 50))
    image.save(path)
    return path
def _game_step(chosen: str, relic: str = "burning_blood") -> GameStep:
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
            cards=[],
            relics=[],
        ),
        actions=[
            ActionCandidate(action_type="pick_card", option_id="anger", screen_box=(1, 2, 3, 4), legal=True),
            ActionCandidate(action_type="skip_reward", option_id="skip", screen_box=(5, 6, 7, 8), legal=True),
        ],
        chosen_action_id=chosen,
        outcome=StepOutcome(victory=relic == "burning_blood", floor_reached=2, hp_remaining=70),
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )


def test_cli_capture_writes_unlabeled_game_step(tmp_path: Path) -> None:
    image_path = _reward_image(tmp_path / "reward.png")
    output = tmp_path / "captures.jsonl"

    exit_code = cli.main(
        [
            "capture",
            "--screenshot",
            str(image_path),
            "--out",
            str(output),
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--character",
            "ironclad",
            "--ascension",
            "10",
            "--floor",
            "7",
            "--deck",
            "strike,bash",
            "--relics",
            "burning_blood",
            "--hp",
            "42",
            "--gold",
            "99",
            "--max-hp",
            "80",
            "--block",
            "5",
            "--energy",
            "3",
            "--turn",
            "2",
            "--strength",
            "1",
            "--dexterity",
            "0",
            "--vulnerable",
            "0",
            "--weak",
            "1",
            "--frail",
            "0",
            "--artifact",
            "0",
            "--poison",
            "0",
            "--regen",
            "0",
            "--intangible",
            "0",
        ]
    )

    assert exit_code == 0
    step = json.loads(output.read_text().splitlines()[0])
    assert step["chosen_action_id"] is None
    assert step["state"]["ascension"] == 10
    assert step["state"]["floor"] == 7
    assert [card["card_id"] for card in step["state"]["cards"]] == ["strike", "bash"]
    assert [relic["relic_id"] for relic in step["state"]["relics"]] == ["burning_blood"]
    assert step["state"]["player"]["hp"] == 42
    assert step["state"]["player"]["max_hp"] == 80
    assert step["state"]["player"]["block"] == 5
    assert step["state"]["player"]["energy"] == 3
    assert step["state"]["player"]["turn"] == 2
    assert step["state"]["player"]["strength"] == 1
    assert step["state"]["player"]["weak"] == 1
    assert step["state"]["player"]["character_resource"]["gold"] == 99
    assert [action["action_type"] for action in step["actions"]] == ["pick_card", "pick_card", "pick_card", "skip_reward"]


def test_cli_capture_maps_detected_relic_count(tmp_path: Path) -> None:
    relic_output = tmp_path / "relic.jsonl"

    relic_code = cli.main(
        [
            "capture",
            "--screenshot",
            str(_relic_image(tmp_path / "relic.png", count=1)),
            "--out",
            str(relic_output),
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

    relic_step = json.loads(relic_output.read_text().splitlines()[0])
    assert relic_code == 0
    assert [action["action_type"] for action in relic_step["actions"]] == ["pick_relic"]


def test_cli_capture_rejects_unknown_screen(tmp_path: Path) -> None:
    unknown_image = tmp_path / "unknown.png"
    Image.new("RGB", (320, 200), (15, 18, 24)).save(unknown_image)

    with pytest.raises(ValueError, match="unknown screen"):
        cli.main(
            [
                "capture",
                "--screenshot",
                str(unknown_image),
                "--out",
                str(tmp_path / "unknown.jsonl"),
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


def test_cli_label_train_and_recommend(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "steps.jsonl"
    dataset.write_text(
        "\n".join(
            [
                _game_step("anger", "burning_blood").to_json(),
                _game_step("skip", "tiny_house").to_json(),
                _game_step("anger", "burning_blood").to_json(),
                _game_step("skip", "tiny_house").to_json(),
            ]
        )
        + "\n"
    )
    model_path = tmp_path / "ironclad.pt"
    step_path = tmp_path / "query.json"
    step_path.write_text(_game_step("anger", "burning_blood").to_json())

    label_code = cli.main(["label", "--dataset", str(dataset), "--index", "1", "--choice", "pick_card:anger"])
    train_code = cli.main(
        [
            "train",
            "--dataset",
            str(dataset),
            "--model",
            str(model_path),
            "--character",
            "ironclad",
            "--epochs",
            "1",
            "--batch-size",
            "2",
            "--device",
            "cpu",
        ]
    )
    recommend_code = cli.main(["recommend", "--model", str(model_path), "--step", str(step_path)])
    output = json.loads(capsys.readouterr().out.splitlines()[-1])

    assert label_code == 0
    assert train_code == 0
    assert recommend_code == 0
    assert output["best"]["action_id"] in {"anger", "skip"}


def test_cli_label_accepts_skip_choice(tmp_path: Path) -> None:
    dataset = tmp_path / "steps.jsonl"
    dataset.write_text(_game_step("anger").to_json() + "\n")

    assert cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "skip"]) == 0
    assert json.loads(dataset.read_text().splitlines()[0])["chosen_action_id"] == "skip"


def test_cli_label_accepts_direct_action_id(tmp_path: Path) -> None:
    dataset = tmp_path / "steps.jsonl"
    dataset.write_text(_game_step("skip").to_json() + "\n")

    assert cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "anger"]) == 0
    assert json.loads(dataset.read_text().splitlines()[0])["chosen_action_id"] == "anger"


def test_cli_label_rejects_missing_pick_option(tmp_path: Path) -> None:
    dataset = tmp_path / "steps.jsonl"
    dataset.write_text(_game_step("anger").to_json() + "\n")

    with pytest.raises(ValueError, match="not present"):
        cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "pick_card:bash"])


def test_cli_label_rejects_skip_when_skip_is_not_an_option(tmp_path: Path) -> None:
    step = GameStep(
        state=_game_step("anger").state,
        actions=[ActionCandidate(action_type="pick_relic", option_id="relic_1", screen_box=(1, 2, 3, 4))],
        chosen_action_id="relic_1",
        outcome=None,
        observation=_game_step("anger").observation,
        screenshot_path=Path("fixture.png"),
    )
    dataset = tmp_path / "steps.jsonl"
    dataset.write_text(step.to_json() + "\n")

    with pytest.raises(ValueError, match="not present"):
        cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "skip"])
