import pytest

from sts2_tas.schema import AutomationAction, TargetWindow, WindowBounds


def test_window_bounds_to_bbox() -> None:
    bounds = WindowBounds(left=100, top=200, width=1280, height=720)

    assert bounds.right == 1380
    assert bounds.bottom == 920
    assert bounds.to_bbox() == (100, 200, 1380, 920)
    assert bounds.to_dict() == {"left": 100, "top": 200, "width": 1280, "height": 720}


def test_window_metadata_validation() -> None:
    with pytest.raises(ValueError, match="positive width"):
        WindowBounds(left=0, top=0, width=0, height=1)
    with pytest.raises(ValueError, match="process"):
        TargetWindow("", "Main Window", WindowBounds(left=0, top=0, width=1, height=1))
    with pytest.raises(ValueError, match="title"):
        TargetWindow("Slay the Spire 2", "", WindowBounds(left=0, top=0, width=1, height=1))


def test_pick_automation_action_requires_target_for_input_plan() -> None:
    action = AutomationAction(action="pick", option_id="anger", dry_run=False, target=None)

    with pytest.raises(ValueError, match="target"):
        action.input_plan()


def test_skip_automation_action_without_target_uses_escape_input_plan() -> None:
    action = AutomationAction(action="skip", option_id=None, dry_run=False, target=None)

    assert action.input_plan() == {"kind": "keypress", "key": "escape"}


def test_action_translates_window_relative_box_to_screen_coordinates() -> None:
    action = AutomationAction(
        action="pick",
        option_id="strike",
        dry_run=True,
        target=(250, 260, 430, 330),
        coordinate_space="window_relative",
        target_window=TargetWindow(
            process="Slay the Spire 2",
            title="Main Window",
            bounds=WindowBounds(left=100, top=200, width=1280, height=720),
        ),
    )

    assert action.input_plan() == {"kind": "click", "x": 440, "y": 495}
    assert action.to_report()["target_window"] == {
        "process": "Slay the Spire 2",
        "title": "Main Window",
        "bounds": {"left": 100, "top": 200, "width": 1280, "height": 720},
    }


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
