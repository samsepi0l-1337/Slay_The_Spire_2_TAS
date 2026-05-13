from pathlib import Path
import json

import pytest

from sts2_tas import automation, cli
from sts2_tas.schema import AutomationAction, DecisionChoice, DecisionSnapshot, TargetWindow, WindowBounds


def _snapshot(path: Path) -> Path:
    path.write_text(
        '{"game_version":"0.105.1","branch":"beta","character":"ironclad","ascension":0,"floor":1,'
        '"deck":["strike"],"relics":["burning_blood"],"hp":70,"gold":0,'
        '"options":[{"id":"strike","name":"Strike","kind":"card","tags":[],"box":[250,260,430,330]},'
        '{"id":"skip","name":"Skip","kind":"skip","tags":[],"box":[880,930,1040,990]}],'
        '"chosen":null,"skipped":false,"screenshot_path":"screen.png"}',
        encoding="utf-8",
    )
    return path


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
            "--snapshot",
            str(_snapshot(tmp_path / "snapshot.json")),
            "--choice",
            "pick:strike",
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


def test_native_input_controller_maps_skip_to_keypress() -> None:
    commands = []
    controller = automation.NativeInputController(
        platform_name="Darwin",
        runner=lambda command: commands.append(command),
    )
    action = AutomationAction(action="skip", option_id=None, dry_run=False, target=None)

    controller.send(action)

    assert commands == [["osascript", "-e", 'tell application "System Events" to key code 53']]


def test_action_translates_window_relative_box_to_target_window_coordinates() -> None:
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
    assert action.to_report()["coordinate_space"] == "window_relative"


def test_plan_action_rejects_target_window_for_default_screen_absolute_snapshot(tmp_path: Path) -> None:
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

    with pytest.raises(ValueError, match="window_relative"):
        automation.plan_action(
            snapshot,
            DecisionChoice(action="pick", option_id="strike"),
            dry_run=True,
            target_window=target_window,
        )


def test_plan_action_accepts_matching_window_relative_snapshot(tmp_path: Path) -> None:
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))
    snapshot = DecisionSnapshot(
        game_version=snapshot.game_version,
        branch=snapshot.branch,
        character=snapshot.character,
        ascension=snapshot.ascension,
        floor=snapshot.floor,
        deck=snapshot.deck,
        relics=snapshot.relics,
        hp=snapshot.hp,
        gold=snapshot.gold,
        options=snapshot.options,
        chosen=snapshot.chosen,
        skipped=snapshot.skipped,
        screenshot_path=snapshot.screenshot_path,
        coordinate_space="window_relative",
        target_window=target_window,
    )

    action = automation.plan_action(
        snapshot,
        DecisionChoice(action="pick", option_id="strike"),
        dry_run=True,
        target_window=target_window,
    )

    assert action.coordinate_space == "window_relative"
    assert action.input_plan() == {"kind": "click", "x": 440, "y": 495}


def test_plan_action_rejects_window_relative_snapshot_without_current_target_window(tmp_path: Path) -> None:
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))
    snapshot = DecisionSnapshot(
        game_version=snapshot.game_version,
        branch=snapshot.branch,
        character=snapshot.character,
        ascension=snapshot.ascension,
        floor=snapshot.floor,
        deck=snapshot.deck,
        relics=snapshot.relics,
        hp=snapshot.hp,
        gold=snapshot.gold,
        options=snapshot.options,
        chosen=snapshot.chosen,
        skipped=snapshot.skipped,
        screenshot_path=snapshot.screenshot_path,
        coordinate_space="window_relative",
        target_window=target_window,
    )

    with pytest.raises(ValueError, match="current target window"):
        automation.plan_action(
            snapshot,
            DecisionChoice(action="pick", option_id="strike"),
            dry_run=True,
        )


def test_plan_action_rejects_mismatched_window_relative_snapshot(tmp_path: Path) -> None:
    captured_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    current_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=101, top=200, width=1280, height=720),
    )
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))
    snapshot = DecisionSnapshot(
        game_version=snapshot.game_version,
        branch=snapshot.branch,
        character=snapshot.character,
        ascension=snapshot.ascension,
        floor=snapshot.floor,
        deck=snapshot.deck,
        relics=snapshot.relics,
        hp=snapshot.hp,
        gold=snapshot.gold,
        options=snapshot.options,
        chosen=snapshot.chosen,
        skipped=snapshot.skipped,
        screenshot_path=snapshot.screenshot_path,
        coordinate_space="window_relative",
        target_window=captured_window,
    )

    with pytest.raises(ValueError, match="target window metadata"):
        automation.plan_action(
            snapshot,
            DecisionChoice(action="pick", option_id="strike"),
            dry_run=True,
            target_window=current_window,
        )


def test_native_input_controller_verifies_target_window_before_input() -> None:
    commands = []
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

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
    target_window = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )

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


def test_native_input_controller_fails_closed_when_target_window_changes() -> None:
    expected = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    moved = TargetWindow(
        process="Slay the Spire 2",
        title="Main Window",
        bounds=WindowBounds(left=101, top=200, width=1280, height=720),
    )

    class Detector:
        def detect(self, process: str) -> TargetWindow:
            return moved

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
                target_window=expected,
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

    subprocess_calls = []
    monkeypatch.setattr(automation.subprocess, "run", lambda command, check: subprocess_calls.append((command, check)))
    automation.NativeInputController(platform_name="Windows").send(
        AutomationAction(action="skip", option_id=None, dry_run=False, target=(880, 930, 1040, 990))
    )

    assert commands == [
        ["osascript", "-e", 'tell application "System Events" to click at {340, 295}'],
        ["xdotool", "mousemove", "340", "295", "click", "1"],
        ["xdotool", "key", "escape"],
    ]
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


def test_native_input_controller_rejects_unsupported_platforms() -> None:
    action = AutomationAction(action="pick", option_id="strike", dry_run=False, target=(250, 260, 430, 330))

    with pytest.raises(RuntimeError, match="not supported on Windows"):
        automation.NativeInputController(platform_name="Windows", runner=lambda command: None).send(action)
    with pytest.raises(RuntimeError, match="unsupported native input platform"):
        automation.NativeInputController(platform_name="Plan9", runner=lambda command: None).send(action)


def test_plan_action_uses_skip_box_when_available(tmp_path: Path) -> None:
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))

    action = automation.plan_action(snapshot, DecisionChoice(action="skip"), dry_run=True)

    assert action.target == (880, 930, 1040, 990)
    assert action.input_plan() == {"kind": "click", "x": 960, "y": 960}


def test_cli_act_rejects_native_without_execute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --execute"):
        cli.main(
            [
                "act",
                "--snapshot",
                str(_snapshot(tmp_path / "snapshot.json")),
                "--choice",
                "pick:strike",
                "--input-log",
                str(tmp_path / "inputs.jsonl"),
                "--input-backend",
                "native",
            ]
        )
