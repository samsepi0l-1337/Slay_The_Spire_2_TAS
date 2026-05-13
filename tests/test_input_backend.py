from pathlib import Path
import json

import pytest

from sts2_tas import automation, cli
from sts2_tas.schema import AutomationAction, DecisionChoice, DecisionSnapshot


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
