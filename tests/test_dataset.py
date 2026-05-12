from pathlib import Path

from sts2_tas.dataset import append_snapshot, candidate_rows, load_snapshots, write_snapshots
from sts2_tas.schema import ChoiceOption, DecisionChoice, DecisionSnapshot


def _snapshot(chosen: DecisionChoice | None) -> DecisionSnapshot:
    return DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=1,
        floor=3,
        deck=["strike", "defend", "bash"],
        relics=["burning_blood"],
        hp=65,
        gold=52,
        options=[
            ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
            ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
        ],
        chosen=chosen,
        skipped=chosen is not None and chosen.action == "skip",
        screenshot_path=Path("fixtures/card.png"),
    )


def test_jsonl_append_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "snapshots.jsonl"
    snapshot = _snapshot(DecisionChoice(action="pick", option_id="anger"))

    append_snapshot(path, snapshot)

    assert load_snapshots(path) == [snapshot]


def test_write_snapshots_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "snapshots.jsonl"

    write_snapshots(path, [_snapshot(DecisionChoice(action="skip"))])
    write_snapshots(path, [_snapshot(DecisionChoice(action="pick", option_id="anger"))])

    assert load_snapshots(path)[0].chosen == DecisionChoice(action="pick", option_id="anger")


def test_candidate_rows_skip_unlabeled_snapshots() -> None:
    rows = candidate_rows(
        [
            _snapshot(None),
            _snapshot(DecisionChoice(action="pick", option_id="anger")),
            _snapshot(DecisionChoice(action="skip")),
        ]
    )

    labels = [label for _, label in rows]
    option_ids = [features["option_id"] for features, _ in rows]

    assert labels == [1, 0, 0, 1]
    assert option_ids == ["anger", "skip", "anger", "skip"]
