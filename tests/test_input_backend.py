from pathlib import Path
import json

import pytest

from sts2_tas import automation, cli
from sts2_tas.schema import (
    ActionCandidate,
    AutomationAction,
    GameStep,
    ObservationQuality,
    PlayerState,
    StructuredGameState,
    TargetWindow,
    WindowBounds,
)


def _step(path: Path, *, actions: list[ActionCandidate] | None = None) -> Path:
    step = GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=actions
        or [
            ActionCandidate(action_type="pick_card", option_id="strike", screen_box=(250, 260, 430, 330)),
            ActionCandidate(action_type="skip_reward", option_id="skip", screen_box=(880, 930, 1040, 990)),
        ],
        chosen_action_id=None,
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("screen.png"),
    )
    path.write_text(step.to_json(), encoding="utf-8")
    return path


def _target_window(left: int = 100) -> TargetWindow:
    return TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=left, top=200, width=1280, height=720),
    )


def test_cli_act_native_execute_sends_click_without_jsonl_event(monkeypatch, tmp_path: Path, capsys) -> None:
    sent = []

    class Controller:
        def send(self, action: AutomationAction) -> None:
            sent.append(action.to_event())

    monkeypatch.setattr(cli, "NativeInputController", lambda: Controller())

    input_log = tmp_path / "inputs.jsonl"
    exit_code = cli.main(
        [
            "act",
            "--step",
            str(_step(tmp_path / "step.json")),
            "--choice",
            "pick_card:strike",
            "--input-log",
            str(input_log),
            "--input-backend",
            "native",
            "--execute",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert sent == [
        {
            "action": "pick",
            "option_id": "strike",
            "target": [250, 260, 430, 330],
            "coordinate_space": "screen_absolute",
            "input_plan": {"kind": "click", "x": 340, "y": 295},
        }
    ]
    assert output["input_plan"] == {"kind": "click", "x": 340, "y": 295}
    assert not input_log.exists()


def test_cli_act_target_process_requires_explicit_window_relative_coordinates(
    monkeypatch, tmp_path: Path
) -> None:
    class Detector:
        def detect(self, process: str) -> TargetWindow:
            raise AssertionError("target detection should not run for an invalid coordinate contract")

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    with pytest.raises(ValueError, match="--coordinate-space window_relative"):
        cli.main(
            [
                "act",
                "--step",
                str(_step(tmp_path / "step.json")),
                "--choice",
                "pick_card:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
                "--target-process",
                "Slay the Spire 2",
            ]
        )


def test_cli_act_target_process_accepts_window_relative_coordinates(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    class Detector:
        def detect(self, process: str) -> TargetWindow:
            assert process == "Slay the Spire 2"
            return _target_window()

    monkeypatch.setattr(cli, "WindowDetector", lambda: Detector())

    exit_code = cli.main(
        [
            "act",
            "--step",
            str(_step(tmp_path / "step.json")),
            "--choice",
            "pick_card:strike",
            "--input-log",
            str(tmp_path / "inputs.jsonl"),
            "--target-process",
            "Slay the Spire 2",
            "--coordinate-space",
            "window_relative",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["coordinate_space"] == "window_relative"
    assert output["input_plan"] == {"kind": "click", "x": 440, "y": 495}
    assert output["target_window"]["process"] == "Slay the Spire 2"


def test_native_input_controller_maps_skip_to_keypress() -> None:
    commands = []
    controller = automation.NativeInputController(
        platform_name="Darwin",
        runner=lambda command: commands.append(command),
    )
    action = AutomationAction(action="skip", option_id=None, dry_run=False, target=None)

    controller.send(action)

    assert commands == [["osascript", "-e", 'tell application "System Events" to key code 53']]


def test_plan_action_maps_combat_end_turn_to_turn_keypress(tmp_path: Path) -> None:
    step = GameStep.from_json(
        _step(
            tmp_path / "step.json",
            actions=[ActionCandidate(action_type="end_turn")],
        ).read_text(encoding="utf-8")
    )

    action = automation.plan_action(step, "end_turn", dry_run=True)

    assert action.action == "skip"
    assert action.option_id == "end_turn"
    assert action.input_plan() == {"kind": "keypress", "key": "e"}
    assert action.to_event()["key"] == "e"


def test_native_input_controller_maps_end_turn_keypress_commands() -> None:
    commands = []
    action = AutomationAction(action="skip", option_id="end_turn", dry_run=False, target=None, key="e")

    automation.NativeInputController(platform_name="Darwin", runner=commands.append).send(action)
    automation.NativeInputController(platform_name="Linux", runner=commands.append).send(action)
    automation.NativeInputController(platform_name="Windows", runner=commands.append).send(action)

    assert commands[0] == ["osascript", "-e", 'tell application "System Events" to keystroke "e"']
    assert commands[1] == ["xdotool", "key", "e"]
    assert commands[2] == [
        "powershell",
        "-NoProfile",
        "-Command",
        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('e')",
    ]


def test_automation_action_rejects_empty_keypress_key() -> None:
    with pytest.raises(ValueError, match="keypress key"):
        AutomationAction(action="skip", option_id="end_turn", dry_run=False, target=None, key="")


def test_plan_action_rejects_target_window_for_screen_absolute_step(tmp_path: Path) -> None:
    step = GameStep.from_json(_step(tmp_path / "step.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="window_relative"):
        automation.plan_action(step, "strike", dry_run=True, target_window=_target_window())


def test_plan_action_accepts_window_relative_step(tmp_path: Path) -> None:
    step = GameStep.from_json(_step(tmp_path / "step.json").read_text(encoding="utf-8"))

    action = automation.plan_action(
        step,
        "strike",
        dry_run=True,
        target_window=_target_window(),
        coordinate_space="window_relative",
    )

    assert action.coordinate_space == "window_relative"
    assert action.input_plan() == {"kind": "click", "x": 440, "y": 495}


def test_plan_action_builds_multi_click_sequence_for_targeted_combat_action(tmp_path: Path) -> None:
    step = GameStep.from_json(
        _step(
            tmp_path / "step.json",
            actions=[
                ActionCandidate(
                    action_type="play_card",
                    source_card_id="hand-0-strike",
                    target_monster_id="jaw_worm:0",
                    screen_box=(100, 800, 220, 980),
                    target_screen_box=(1200, 310, 1520, 620),
                )
            ],
        ).read_text(encoding="utf-8")
    )

    action = automation.plan_action(step, "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0", dry_run=True)

    assert action.target == (100, 800, 220, 980)
    assert action.targets == [(100, 800, 220, 980), (1200, 310, 1520, 620)]
    assert action.to_event()["targets"] == [[100, 800, 220, 980], [1200, 310, 1520, 620]]
    assert action.input_plan() == {
        "kind": "sequence",
        "steps": [
            {"kind": "click", "x": 160, "y": 890},
            {"kind": "click", "x": 1360, "y": 465},
        ],
    }


def test_plan_action_rejects_window_relative_without_current_target_window(tmp_path: Path) -> None:
    step = GameStep.from_json(_step(tmp_path / "step.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="current target window"):
        automation.plan_action(step, "strike", dry_run=True, coordinate_space="window_relative")


def test_plan_action_rejects_missing_illegal_or_targetless_actions(tmp_path: Path) -> None:
    step = GameStep.from_json(
        _step(
            tmp_path / "step.json",
            actions=[
                ActionCandidate(action_type="pick_card", option_id="strike", legal=False, screen_box=(1, 2, 3, 4)),
                ActionCandidate(action_type="pick_card", option_id="bash", legal=True),
                ActionCandidate(
                    action_type="play_card",
                    source_card_id="hand-0-strike",
                    target_monster_id="jaw_worm:0",
                    legal=True,
                    screen_box=(100, 800, 220, 980),
                ),
            ],
        ).read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="not present"):
        automation.plan_action(step, "missing", dry_run=True)
    with pytest.raises(ValueError, match="not legal"):
        automation.plan_action(step, "strike", dry_run=True)
    with pytest.raises(ValueError, match="no screen target"):
        automation.plan_action(step, "bash", dry_run=True)
    with pytest.raises(ValueError, match="no target screen box"):
        automation.plan_action(step, "play_card:source_card=hand-0-strike|target_monster=jaw_worm:0", dry_run=True)


def test_native_input_controller_verifies_target_window_before_input() -> None:
    commands = []
    target_window = _target_window()

    class Detector:
        def detect(self, process: str) -> TargetWindow:
            assert process == "Slay the Spire 2"
            return target_window

    controller = automation.NativeInputController(
        platform_name="Darwin",
        runner=commands.append,
        window_detector=Detector(),
    )

    controller.send(
        AutomationAction(
            action="pick",
            option_id="strike",
            dry_run=False,
            target=(250, 260, 430, 330),
            coordinate_space="window_relative",
            target_window=target_window,
        )
    )

    script = commands[0][-1]
    assert commands[0][:2] == ["osascript", "-e"]
    assert 'tell application "Slay the Spire 2" to activate' in script
    assert "error \"target window changed before input\"" in script
    assert "expectedLeft" in script
    assert "expectedTop" in script
    assert "expectedWidth" in script
    assert "expectedHeight" in script
    _assert_target_action_runs_inside_guard(script, "click at {440, 495}")


def test_native_input_controller_keeps_target_keypress_inside_window_guard() -> None:
    commands = []
    target_window = _target_window()

    class Detector:
        def detect(self, process: str) -> TargetWindow:
            return target_window

    controller = automation.NativeInputController(
        platform_name="Darwin",
        runner=commands.append,
        window_detector=Detector(),
    )

    controller.send(
        AutomationAction(
            action="skip",
            option_id=None,
            dry_run=False,
            target=None,
            coordinate_space="window_relative",
            target_window=target_window,
        )
    )

    _assert_target_action_runs_inside_guard(commands[0][-1], "key code 53")


def test_windows_native_input_keeps_target_guard_and_click_in_one_script() -> None:
    commands = []
    target_window = _target_window()

    class Detector:
        def detect(self, process: str) -> TargetWindow:
            assert process == "Slay the Spire 2"
            return target_window

    controller = automation.NativeInputController(
        platform_name="Windows",
        runner=commands.append,
        window_detector=Detector(),
    )

    controller.send(
        AutomationAction(
            action="pick",
            option_id="strike",
            dry_run=False,
            target=(250, 260, 430, 330),
            coordinate_space="window_relative",
            target_window=target_window,
        )
    )

    script = commands[0][-1]
    assert commands[0][:3] == ["powershell", "-NoProfile", "-Command"]
    assert "SetForegroundWindow" in script
    assert "GetWindowRect" in script
    assert "target window changed before input" in script
    assert script.index("target window changed before input") < script.index("[Win32Input]::mouse_event")


def test_windows_native_input_keeps_target_guard_and_keypress_in_one_script() -> None:
    commands = []
    target_window = _target_window()

    class Detector:
        def detect(self, process: str) -> TargetWindow:
            return target_window

    controller = automation.NativeInputController(
        platform_name="Windows",
        runner=commands.append,
        window_detector=Detector(),
    )

    controller.send(
        AutomationAction(
            action="skip",
            option_id=None,
            dry_run=False,
            target=None,
            coordinate_space="window_relative",
            target_window=target_window,
        )
    )

    script = commands[0][-1]
    assert "SetForegroundWindow" in script
    assert "target window changed before input" in script
    assert script.index("target window changed before input") < script.index("SendKeys")


def test_native_input_controller_fails_closed_when_target_window_changes() -> None:
    class Detector:
        def detect(self, process: str) -> TargetWindow:
            return _target_window(left=101)

    controller = automation.NativeInputController(
        platform_name="Darwin",
        runner=lambda command: None,
        window_detector=Detector(),
    )

    with pytest.raises(RuntimeError, match="target window changed before input"):
        controller.send(
            AutomationAction(
                action="skip",
                option_id=None,
                dry_run=False,
                target=None,
                coordinate_space="window_relative",
                target_window=_target_window(),
            )
        )


def _assert_target_action_runs_inside_guard(script: str, action_line: str) -> None:
    last_bounds_check = script.index("if item 2 of windowSize is not expectedHeight")
    first_end_tell = script.index("end tell")
    action_index = script.index(action_line)
    assert last_bounds_check < action_index < first_end_tell


def test_native_input_controller_maps_platform_commands(monkeypatch) -> None:
    commands = []
    action = AutomationAction(action="pick", option_id="strike", dry_run=False, target=(250, 260, 430, 330))

    automation.NativeInputController(platform_name="Darwin", runner=commands.append).send(action)
    automation.NativeInputController(platform_name="Linux", runner=commands.append).send(action)
    automation.NativeInputController(
        platform_name="Linux",
        runner=commands.append,
    ).send(AutomationAction(action="skip", option_id=None, dry_run=False, target=None))
    automation.NativeInputController(platform_name="Windows", runner=commands.append).send(action)

    subprocess_calls = []
    monkeypatch.setattr(automation.subprocess, "run", lambda command, check: subprocess_calls.append((command, check)))
    automation.NativeInputController(platform_name="Windows").send(
        AutomationAction(action="skip", option_id=None, dry_run=False, target=(880, 930, 1040, 990))
    )

    assert commands[:3] == [
        ["osascript", "-e", 'tell application "System Events" to click at {340, 295}'],
        ["xdotool", "mousemove", "340", "295", "click", "1"],
        ["xdotool", "key", "escape"],
    ]
    assert commands[3][:3] == ["powershell", "-NoProfile", "-Command"]
    windows_click_script = commands[3][-1]
    assert "SetCursorPos" in windows_click_script
    assert "mouse_event" in windows_click_script
    assert windows_click_script.index("throw 'SetCursorPos failed'") < windows_click_script.index(
        "[Win32Input]::mouse_event"
    )
    assert "340" in windows_click_script
    assert "295" in windows_click_script
    assert subprocess_calls == [
        (
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{ESC}')",
            ],
            True,
        )
    ]


def test_native_input_controller_maps_multi_click_sequence() -> None:
    commands = []
    action = AutomationAction(
        action="pick",
        option_id="play_card|source_card=hand-0-strike|target_monster=jaw_worm:0",
        dry_run=False,
        target=(100, 800, 220, 980),
        targets=[(100, 800, 220, 980), (1200, 310, 1520, 620)],
    )

    automation.NativeInputController(platform_name="Darwin", runner=commands.append).send(action)
    automation.NativeInputController(platform_name="Linux", runner=commands.append).send(action)
    automation.NativeInputController(platform_name="Windows", runner=commands.append).send(action)

    assert commands[0] == [
        "osascript",
        "-e",
        'tell application "System Events"\n  click at {160, 890}\n  click at {1360, 465}\nend tell',
    ]
    assert commands[1] == [
        "xdotool",
        "mousemove",
        "160",
        "890",
        "click",
        "1",
        "mousemove",
        "1360",
        "465",
        "click",
        "1",
    ]
    assert commands[2][:3] == ["powershell", "-NoProfile", "-Command"]
    assert commands[2][-1].count("[Win32Input]::mouse_event(0x0002") == 2
    assert "SetCursorPos(160, 890)" in commands[2][-1]
    assert "SetCursorPos(1360, 465)" in commands[2][-1]


def test_native_input_controller_rejects_unsupported_platforms() -> None:
    action = AutomationAction(action="pick", option_id="strike", dry_run=False, target=(250, 260, 430, 330))

    with pytest.raises(RuntimeError, match="unsupported native input platform"):
        automation.NativeInputController(platform_name="Plan9", runner=lambda command: None).send(action)


def test_plan_action_uses_skip_box_when_available(tmp_path: Path) -> None:
    step = GameStep.from_json(_step(tmp_path / "step.json").read_text(encoding="utf-8"))

    action = automation.plan_action(step, "skip", dry_run=True)

    assert action.target == (880, 930, 1040, 990)
    assert action.input_plan() == {"kind": "click", "x": 960, "y": 960}


def test_cli_act_rejects_native_without_execute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --execute"):
        cli.main(
            [
                "act",
                "--step",
                str(_step(tmp_path / "step.json")),
                "--choice",
                "pick_card:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
                "--input-backend",
                "native",
            ]
        )
