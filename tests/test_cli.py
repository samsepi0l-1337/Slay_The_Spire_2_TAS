import json
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from sts2_tas import cli
from sts2_tas.schema import ChoiceOption, DecisionChoice, DecisionSnapshot


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


def _snapshot(choice: DecisionChoice, relic: str) -> DecisionSnapshot:
    return DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=["strike", "defend"],
        relics=[relic],
        hp=70,
        gold=99,
        options=[
            ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
            ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
        ],
        chosen=choice,
        skipped=choice.action == "skip",
        screenshot_path=Path("fixture.png"),
    )


def test_cli_capture_writes_unlabeled_snapshot(tmp_path: Path) -> None:
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
        ]
    )

    assert exit_code == 0
    snapshot = json.loads(output.read_text().splitlines()[0])
    assert snapshot["chosen"] is None
    assert snapshot["ascension"] == 10
    assert snapshot["floor"] == 7
    assert snapshot["deck"] == ["strike", "bash"]
    assert snapshot["relics"] == ["burning_blood"]
    assert snapshot["hp"] == 42
    assert snapshot["gold"] == 99


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

    relic_snapshot = json.loads(relic_output.read_text().splitlines()[0])
    assert relic_code == 0
    assert [option["kind"] for option in relic_snapshot["options"]] == ["relic"]


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
    dataset = tmp_path / "snapshots.jsonl"
    dataset.write_text(
        "\n".join(
            [
                _snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json(),
                _snapshot(DecisionChoice(action="skip"), "tiny_house").to_json(),
            ]
        )
        + "\n"
    )
    model_path = tmp_path / "ironclad.joblib"
    query_path = tmp_path / "query.json"
    query_path.write_text(_snapshot(DecisionChoice(action="skip"), "tiny_house").to_json())

    label_code = cli.main(["label", "--dataset", str(dataset), "--index", "1", "--choice", "pick:anger"])
    train_code = cli.main(["train", "--dataset", str(dataset), "--model", str(model_path), "--character", "ironclad"])
    recommend_code = cli.main(["recommend", "--model", str(model_path), "--snapshot", str(query_path)])
    output = json.loads(capsys.readouterr().out.splitlines()[-1])

    assert label_code == 0
    assert train_code == 0
    assert recommend_code == 0
    assert output["best"]["option_id"] == "anger"


def test_cli_migrates_legacy_dataset_and_trains_torch_backend(tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "snapshots.jsonl"
    dataset.write_text(
        "\n".join(
            [
                _snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json(),
                _snapshot(DecisionChoice(action="skip"), "tiny_house").to_json(),
                _snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json(),
                _snapshot(DecisionChoice(action="skip"), "tiny_house").to_json(),
            ]
        )
        + "\n"
    )
    steps = tmp_path / "steps.jsonl"
    model_path = tmp_path / "ironclad.pt"
    query_path = tmp_path / "query.json"
    query_path.write_text(_snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json())

    migrate_code = cli.main(["migrate-dataset", "--in", str(dataset), "--out", str(steps), "--catalog-version", "test-catalog"])
    train_code = cli.main(
        [
            "train",
            "--dataset",
            str(steps),
            "--model",
            str(model_path),
            "--character",
            "ironclad",
            "--backend",
            "torch",
            "--epochs",
            "2",
            "--batch-size",
            "2",
            "--device",
            "cpu",
        ]
    )
    recommend_code = cli.main(["recommend", "--model", str(model_path), "--snapshot", str(query_path), "--backend", "torch"])
    output = json.loads(capsys.readouterr().out.splitlines()[-1])

    assert migrate_code == 0
    assert train_code == 0
    assert recommend_code == 0
    assert model_path.exists()
    assert json.loads(steps.read_text().splitlines()[0])["state"]["catalog_version"] == "test-catalog"
    assert output["best"]["option_id"] in {"anger", "skip"}


def test_cli_recommend_rejects_backend_model_suffix_mismatch(tmp_path: Path) -> None:
    query_path = tmp_path / "query.json"
    query_path.write_text(_snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json())

    with pytest.raises(ValueError, match="sklearn backend"):
        cli.main(["recommend", "--model", str(tmp_path / "model.pt"), "--snapshot", str(query_path), "--backend", "sklearn"])
    with pytest.raises(ValueError, match="torch backend"):
        cli.main(["recommend", "--model", str(tmp_path / "model.joblib"), "--snapshot", str(query_path), "--backend", "torch"])


def test_cli_label_accepts_skip_choice(tmp_path: Path) -> None:
    dataset = tmp_path / "snapshots.jsonl"
    dataset.write_text(_snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json() + "\n")

    assert cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "skip"]) == 0
    assert json.loads(dataset.read_text().splitlines()[0])["chosen"]["action"] == "skip"


def test_cli_label_rejects_missing_pick_option(tmp_path: Path) -> None:
    dataset = tmp_path / "snapshots.jsonl"
    dataset.write_text(_snapshot(DecisionChoice(action="pick", option_id="anger"), "burning_blood").to_json() + "\n")

    with pytest.raises(ValueError, match="not present"):
        cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "pick:bash"])


def test_cli_label_rejects_skip_when_skip_is_not_an_option(tmp_path: Path) -> None:
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=70,
        gold=0,
        options=[ChoiceOption(id="relic_1", name="Relic 1", kind="relic", tags=[])],
        chosen=DecisionChoice(action="pick", option_id="relic_1"),
        skipped=False,
        screenshot_path=Path("fixture.png"),
    )
    dataset = tmp_path / "snapshots.jsonl"
    dataset.write_text(snapshot.to_json() + "\n")

    with pytest.raises(ValueError, match="skip option"):
        cli.main(["label", "--dataset", str(dataset), "--index", "0", "--choice", "skip"])
