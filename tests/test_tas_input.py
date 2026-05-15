from pathlib import Path

import pytest

from sts2_tas import automation, tas_input
from sts2_tas.schema import (
    ActionCandidate,
    GameStep,
    ObservationQuality,
    PlayerState,
    StructuredGameState,
)


def _combat_step(*, actions: list[ActionCandidate]) -> GameStep:
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="tas-input-test",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="combat",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=actions,
        chosen_action_id=None,
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "tas-input-test"),
        screenshot_path=Path("combat.png"),
    )


def test_play_card_without_target_is_slot_keypress_only() -> None:
    step = _combat_step(
        actions=[
            ActionCandidate(
                action_type="play_card",
                source_card_id="hand-0-strike",
            ),
        ]
    )
    action = automation.plan_action(step, "play_card:source_card=hand-0-strike", dry_run=True)

    assert action.action == "skip"
    assert action.key == "1"
    assert action.target is None
    assert action.targets is None
    assert action.input_plan() == {"kind": "keypress", "key": "1"}


def test_play_card_with_monster_target_prefixes_key_and_target_click() -> None:
    step = _combat_step(
        actions=[
            ActionCandidate(
                action_type="play_card",
                source_card_id="hand-1-strike",
                target_monster_id="jaw_worm:0",
                target_screen_box=(1200, 310, 1520, 620),
            )
        ]
    )
    action = automation.plan_action(
        step, "play_card:source_card=hand-1-strike|target_monster=jaw_worm:0", dry_run=True
    )

    assert action.key == "2"
    assert action.targets == [(1200, 310, 1520, 620)]
    assert action.input_plan() == {
        "kind": "sequence",
        "steps": [
            {"kind": "keypress", "key": "2"},
            {"kind": "click", "x": 1360, "y": 465},
        ],
    }
    command = tas_input.build_dry_run_command(action, platform_name="Windows")
    assert "SendWait('2')" in command[3]
    assert "SetCursorPos(1360, 465)" in command[3]


def test_choose_path_and_event_actions_keep_click_plan() -> None:
    choose_path = automation.plan_action(
        _combat_step(
            actions=[
                ActionCandidate(
                    action_type="choose_path",
                    path_node_id="0",
                    screen_box=(100, 200, 300, 280),
                )
            ]
        ),
        "choose_path:path_node=0",
        dry_run=True,
    )
    choose_event = automation.plan_action(
        _combat_step(
            actions=[
                ActionCandidate(
                    action_type="choose_event_option",
                    event_option_id="proceed",
                    screen_box=(30, 60, 130, 140),
                )
            ]
        ),
        "choose_event_option:event_option=proceed",
        dry_run=True,
    )
    skip_reward = automation.plan_action(
        _combat_step(
            actions=[
                ActionCandidate(
                    action_type="skip_reward",
                    option_id="skip",
                    screen_box=(10, 20, 110, 80),
                )
            ]
        ),
        "skip",
        dry_run=True,
    )

    assert choose_path.input_plan() == {"kind": "click", "x": 200, "y": 240}
    assert choose_event.input_plan() == {"kind": "click", "x": 80, "y": 100}
    assert skip_reward.input_plan() == {"kind": "click", "x": 60, "y": 50}


def test_plan_action_rejects_missing_click_or_target_boxes() -> None:
    with pytest.raises(ValueError, match="screen target"):
        automation.plan_action(
            _combat_step(actions=[ActionCandidate(action_type="choose_path", path_node_id="0")]),
            "choose_path:path_node=0",
            dry_run=True,
        )
    with pytest.raises(ValueError, match="target screen box"):
        automation.plan_action(
            _combat_step(
                actions=[
                    ActionCandidate(
                        action_type="play_card",
                        source_card_id="hand-0-strike",
                        target_monster_id="jaw_worm:0",
                    )
                ]
            ),
            "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0",
            dry_run=True,
        )
    with pytest.raises(ValueError, match="target screen box"):
        automation.plan_action(
            _combat_step(
                actions=[
                    ActionCandidate(
                        action_type="choose_event_option",
                        event_option_id="attack",
                        screen_box=(1, 2, 3, 4),
                        target_monster_id="jaw_worm:0",
                    )
                ]
            ),
            "choose_event_option|target_monster=jaw_worm:0|event_option=attack",
            dry_run=True,
        )


def test_windows_dry_run_command_can_be_built_from_action_plan() -> None:
    action = automation.plan_action(
        _combat_step(
            actions=[
                ActionCandidate(
                    action_type="play_card",
                    source_card_id="hand-1-strike",
                    target_monster_id="jaw_worm:0",
                    target_screen_box=(1200, 310, 1520, 620),
                )
            ]
        ),
        "play_card:source_card=hand-1-strike|target_monster=jaw_worm:0",
        dry_run=True,
    )
    command = tas_input.build_dry_run_command(action, platform_name="Windows")

    assert command[:3] == ["powershell", "-NoProfile", "-Command"]
    assert "SendWait('2')" in command[3]
    assert command[3].count("[Win32Input]::mouse_event(0x0002") == 1
    assert "SetCursorPos(1360, 465)" in command[3]


def test_windows_native_plan_clicks_end_turn_target_when_present() -> None:
    action = automation.plan_action(
        _combat_step(actions=[ActionCandidate(action_type="end_turn", screen_box=(1700, 840, 1810, 930))]),
        "end_turn",
        dry_run=True,
    )

    command = tas_input.build_dry_run_command(action, platform_name="Windows")

    assert "SendWait('e')" in command[3]
    assert "SetCursorPos(1755, 885)" in command[3]


def test_play_card_slot_rejects_ambiguous_or_out_of_range_hand_ids() -> None:
    for source_card_id in ("hand-10-strike", "hand-99-strike", "hand-01-strike"):
        with pytest.raises(ValueError, match="hand slot"):
            tas_input.play_card_slot_key(source_card_id)


def test_automation_action_rejects_invalid_click_boxes() -> None:
    invalid_boxes = [
        (10, 10, 10, 20),
        (20, 10, 10, 20),
        (-1, 10, 10, 20),
    ]
    for box in invalid_boxes:
        with pytest.raises(ValueError, match="click box"):
            automation.plan_action(
                _combat_step(actions=[ActionCandidate(action_type="choose_path", path_node_id="0", screen_box=box)]),
                "choose_path:path_node=0",
                dry_run=True,
            )


def test_non_card_targeted_action_uses_source_and_target_click_sequence() -> None:
    action = automation.plan_action(
        _combat_step(
            actions=[
                ActionCandidate(
                    action_type="choose_event_option",
                    event_option_id="attack",
                    screen_box=(10, 20, 110, 120),
                    target_monster_id="jaw_worm:0",
                    target_screen_box=(1200, 310, 1520, 620),
                )
            ]
        ),
        "choose_event_option|target_monster=jaw_worm:0|event_option=attack",
        dry_run=True,
    )

    assert action.targets == [(10, 20, 110, 120), (1200, 310, 1520, 620)]
    assert action.input_plan()["steps"] == [
        {"kind": "click", "x": 60, "y": 70},
        {"kind": "click", "x": 1360, "y": 465},
    ]


def test_play_card_slot_key_parsing() -> None:
    assert tas_input.play_card_slot_key("hand-0-strike") == "1"
    assert tas_input.play_card_slot_key("hand-9-strike") == "0"


def test_play_card_slot_key_rejects_invalid_source_card_id() -> None:
    with pytest.raises(ValueError, match="cannot parse hand slot"):
        tas_input.play_card_slot_key("hand-strike")
    with pytest.raises(ValueError, match="supported range"):
        tas_input.play_card_slot_key("hand-10-strike")


def test_build_play_card_plan_rejects_non_play_card_or_incomplete_candidate() -> None:
    with pytest.raises(ValueError, match="only play_card"):
        tas_input.build_play_card_plan(ActionCandidate(action_type="end_turn"))
    with pytest.raises(ValueError, match="source_card_id"):
        tas_input.build_play_card_plan(ActionCandidate(action_type="play_card"))
    with pytest.raises(ValueError, match="target screen box"):
        tas_input.build_play_card_plan(
            ActionCandidate(
                action_type="play_card",
                source_card_id="hand-0-strike",
                target_monster_id="jaw_worm:0",
            )
        )
