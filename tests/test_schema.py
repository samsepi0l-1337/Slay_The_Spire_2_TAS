from pathlib import Path

import pytest

from sts2_tas.schema import AutomationAction, ChoiceOption, DecisionChoice, DecisionSnapshot, TargetWindow, WindowBounds


def test_snapshot_round_trips_through_json() -> None:
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=2,
        floor=7,
        deck=["strike", "defend"],
        relics=["burning_blood"],
        hp=42,
        gold=99,
        options=[
            ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
            ChoiceOption(id="bash", name="Bash", kind="card", tags=["vulnerable"]),
        ],
        chosen=DecisionChoice(action="pick", option_id="anger"),
        skipped=False,
        screenshot_path=Path("screenshots/run-1.png"),
    )

    encoded = snapshot.to_json()
    decoded = DecisionSnapshot.from_json(encoded)

    assert decoded == snapshot


def test_window_relative_snapshot_round_trips_target_window_metadata() -> None:
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=2,
        floor=7,
        deck=["strike", "defend"],
        relics=["burning_blood"],
        hp=42,
        gold=99,
        options=[],
        chosen=None,
        skipped=False,
        screenshot_path=Path("screenshots/window.png"),
        coordinate_space="window_relative",
        target_window=target_window,
    )

    encoded = snapshot.to_json()
    decoded = DecisionSnapshot.from_json(encoded)

    assert decoded == snapshot
    assert decoded.to_dict()["target_window"] == target_window.to_dict()


def test_snapshot_allows_unlabeled_capture() -> None:
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="main",
        character="silent",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=70,
        gold=0,
        options=[],
        chosen=None,
        skipped=False,
        screenshot_path=Path("capture.png"),
    )

    assert snapshot.chosen is None


def test_snapshot_rejects_missing_version() -> None:
    with pytest.raises(ValueError, match="game_version"):
        DecisionSnapshot(
            game_version="",
            branch="main",
            character="ironclad",
            ascension=0,
            floor=1,
            deck=[],
            relics=[],
            hp=70,
            gold=0,
            options=[],
            chosen=None,
            skipped=False,
            screenshot_path=Path("capture.png"),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"id": "", "name": "Anger", "kind": "card", "tags": []}, "option id"),
        ({"id": "anger", "name": "", "kind": "card", "tags": []}, "option name"),
        ({"id": "anger", "name": "Anger", "kind": "boss", "tags": []}, "unsupported option kind"),
    ],
)
def test_choice_option_validation(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ChoiceOption(**kwargs)


@pytest.mark.parametrize(
    ("choice", "message"),
    [
        ({"action": "burn"}, "unsupported decision action"),
        ({"action": "pick"}, "option_id"),
        ({"action": "skip", "option_id": "anger"}, "must not include"),
    ],
)
def test_decision_choice_validation(choice, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DecisionChoice(**choice)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("branch", "", "branch"),
        ("character", "", "character"),
        ("ascension", -1, "ascension"),
        ("floor", 0, "floor"),
        ("hp", -1, "hp"),
        ("gold", -1, "gold"),
    ],
)
def test_snapshot_numeric_and_identity_validation(field: str, value, message: str) -> None:
    data = {
        "game_version": "0.105.1",
        "branch": "main",
        "character": "ironclad",
        "ascension": 0,
        "floor": 1,
        "deck": [],
        "relics": [],
        "hp": 70,
        "gold": 0,
        "options": [],
        "chosen": None,
        "skipped": False,
        "screenshot_path": Path("capture.png"),
    }
    data[field] = value

    with pytest.raises(ValueError, match=message):
        DecisionSnapshot(**data)


def test_snapshot_rejects_invalid_coordinate_space() -> None:
    with pytest.raises(ValueError, match="unsupported coordinate_space"):
        DecisionSnapshot(
            game_version="0.105.1",
            branch="main",
            character="ironclad",
            ascension=0,
            floor=1,
            deck=[],
            relics=[],
            hp=70,
            gold=0,
            options=[],
            chosen=None,
            skipped=False,
            screenshot_path=Path("capture.png"),
            coordinate_space="viewport",  # type: ignore[arg-type]
        )


def test_snapshot_rejects_inconsistent_coordinate_metadata() -> None:
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

    with pytest.raises(ValueError, match="screen_absolute"):
        DecisionSnapshot(
            game_version="0.105.1",
            branch="main",
            character="ironclad",
            ascension=0,
            floor=1,
            deck=[],
            relics=[],
            hp=70,
            gold=0,
            options=[],
            chosen=None,
            skipped=False,
            screenshot_path=Path("capture.png"),
            target_window=target_window,
        )
    with pytest.raises(ValueError, match="window_relative"):
        DecisionSnapshot(
            game_version="0.105.1",
            branch="main",
            character="ironclad",
            ascension=0,
            floor=1,
            deck=[],
            relics=[],
            hp=70,
            gold=0,
            options=[],
            chosen=None,
            skipped=False,
            screenshot_path=Path("capture.png"),
            coordinate_space="window_relative",
        )


def test_skip_choice_has_no_option_id() -> None:
    choice = DecisionChoice(action="skip")

    assert choice.option_id is None


def test_pick_automation_action_requires_target_for_input_plan() -> None:
    action = AutomationAction(action="pick", option_id="anger", dry_run=False, target=None)

    with pytest.raises(ValueError, match="target"):
        action.input_plan()


def test_skip_automation_action_without_target_uses_escape_input_plan() -> None:
    action = AutomationAction(action="skip", option_id=None, dry_run=False, target=None)

    assert action.input_plan() == {"kind": "keypress", "key": "escape"}


def test_automation_action_rejects_invalid_coordinate_metadata() -> None:
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

    with pytest.raises(ValueError, match="unsupported coordinate_space"):
        AutomationAction(
            action="skip",
            option_id=None,
            dry_run=False,
            target=None,
            coordinate_space="viewport",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="window_relative"):
        AutomationAction(
            action="skip",
            option_id=None,
            dry_run=False,
            target=None,
            target_window=target_window,
        )
    with pytest.raises(ValueError, match="target_window"):
        AutomationAction(
            action="pick",
            option_id="anger",
            dry_run=False,
            target=(250, 260, 430, 330),
            coordinate_space="window_relative",
        )
