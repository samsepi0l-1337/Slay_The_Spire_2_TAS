from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .schema import AutomationAction, DecisionChoice, DecisionSnapshot


CommandRunner = Callable[[list[str]], object]


class InputController(Protocol):
    def send(self, action: AutomationAction) -> None:  # pragma: no cover
        ...


@dataclass(frozen=True)
class JsonlInputController:
    log_path: Path

    def send(self, action: AutomationAction) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(action.to_event(), sort_keys=True) + "\n")


@dataclass(frozen=True)
class NativeInputController:
    platform_name: str | None = None
    runner: CommandRunner | None = None

    def send(self, action: AutomationAction) -> None:
        command = _native_command(action, self.platform_name or platform.system())
        runner = self.runner or _run_command
        runner(command)


def plan_action(snapshot: DecisionSnapshot, choice: DecisionChoice, *, dry_run: bool) -> AutomationAction:
    target = None
    if choice.action == "pick":
        option = next((option for option in snapshot.options if option.id == choice.option_id), None)
        if option is None:
            raise ValueError(f"choice option_id is not present in snapshot options: {choice.option_id}")
        target = option.box
    if choice.action == "skip":
        skip_option = next((option for option in snapshot.options if option.kind == "skip"), None)
        if skip_option is None:
            raise ValueError("skip choice requires a skip option in the snapshot")
        target = skip_option.box
    return AutomationAction(action=choice.action, option_id=choice.option_id, dry_run=dry_run, target=target)


def apply_action(action: AutomationAction, controller: InputController | None) -> dict[str, object]:
    if action.dry_run:
        return action.to_report()
    if controller is None:
        raise ValueError("execute mode requires an input controller")
    controller.send(action)
    return action.to_report()


def _run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _native_command(action: AutomationAction, platform_name: str) -> list[str]:
    system = platform_name.lower()
    plan = _native_input_plan(action, system)
    if system == "darwin":
        return _macos_command(plan)
    if system == "linux":
        return _linux_command(plan)
    if system == "windows":
        return _windows_command(plan)
    raise RuntimeError(f"unsupported native input platform: {platform_name}")


def _native_input_plan(action: AutomationAction, system: str) -> dict[str, int | str]:
    if system == "windows" and action.action == "skip":
        return {"kind": "keypress", "key": "escape"}
    return action.input_plan()


def _macos_command(plan: dict[str, int | str]) -> list[str]:
    if plan["kind"] == "click":
        return [
            "osascript",
            "-e",
            f'tell application "System Events" to click at {{{plan["x"]}, {plan["y"]}}}',
        ]
    return ["osascript", "-e", 'tell application "System Events" to key code 53']


def _linux_command(plan: dict[str, int | str]) -> list[str]:
    if plan["kind"] == "click":
        return ["xdotool", "mousemove", str(plan["x"]), str(plan["y"]), "click", "1"]
    return ["xdotool", "key", str(plan["key"])]


def _windows_command(plan: dict[str, int | str]) -> list[str]:
    if plan["kind"] == "click":
        raise RuntimeError("native click input is not supported on Windows")
    return [
        "powershell",
        "-NoProfile",
        "-Command",
        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{ESC}')",
    ]
