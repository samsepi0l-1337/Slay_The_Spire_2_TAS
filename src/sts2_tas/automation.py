from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .schema import AutomationAction, CoordinateSpace, GameStep, TargetWindow
from .windowing import WindowDetector, WindowDetectorProtocol


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
    window_detector: WindowDetectorProtocol | None = None

    def send(self, action: AutomationAction) -> None:
        self._verify_target_window(action)
        command = _native_command(action, self.platform_name or platform.system())
        runner = self.runner or _run_command
        runner(command)

    def _verify_target_window(self, action: AutomationAction) -> None:
        if action.target_window is None:
            return
        detector = self.window_detector or WindowDetector(platform_name=self.platform_name)
        current = detector.detect(action.target_window.process)
        if current != action.target_window:
            raise RuntimeError("target window changed before input")


def plan_action(
    step: GameStep,
    action_id: str,
    *,
    dry_run: bool,
    target_window: TargetWindow | None = None,
    coordinate_space: CoordinateSpace = "screen_absolute",
) -> AutomationAction:
    _validate_target_window(coordinate_space, target_window)
    candidate = next((action for action in step.actions if action.identity == action_id), None)
    if candidate is None:
        raise ValueError(f"action_id is not present in game step actions: {action_id}")
    if not candidate.legal:
        raise ValueError(f"action_id is not legal: {action_id}")
    automation_action = "skip" if candidate.action_type in {"skip_reward", "end_turn"} else "pick"
    option_id = None if automation_action == "skip" else candidate.identity
    target = candidate.screen_box
    if automation_action == "pick" and target is None:
        raise ValueError(f"action_id has no screen target: {action_id}")
    return AutomationAction(
        action=automation_action,
        option_id=option_id,
        dry_run=dry_run,
        target=target,
        coordinate_space=coordinate_space,
        target_window=target_window,
    )


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
    plan = action.input_plan()
    if action.target_window is not None:
        plan["target_process"] = action.target_window.process
        plan["target_title"] = action.target_window.title
        plan["expected_left"] = action.target_window.bounds.left
        plan["expected_top"] = action.target_window.bounds.top
        plan["expected_width"] = action.target_window.bounds.width
        plan["expected_height"] = action.target_window.bounds.height
    return plan


def _macos_command(plan: dict[str, int | str]) -> list[str]:
    target_process = plan.get("target_process")
    if plan["kind"] == "click":
        action = f'click at {{{plan["x"]}, {plan["y"]}}}'
    else:
        action = "key code 53"
    if isinstance(target_process, str):
        return ["osascript", "-e", _macos_target_guard(plan, action)]
    if plan["kind"] == "click":
        return ["osascript", "-e", f'tell application "System Events" to {action}']
    return ["osascript", "-e", f'tell application "System Events" to {action}']


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


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _validate_target_window(coordinate_space: CoordinateSpace, target_window: TargetWindow | None) -> None:
    if coordinate_space == "window_relative" and target_window is None:
        raise ValueError("window_relative actions require a current target window")
    if target_window is not None and coordinate_space != "window_relative":
        raise ValueError("target-process coordinate translation requires a window_relative step")


def _macos_target_guard(plan: dict[str, int | str], action: str) -> str:
    process = _escape_applescript(str(plan["target_process"]))
    title = _escape_applescript(str(plan["target_title"]))
    return (
        f'set expectedProcess to "{process}"\n'
        f'set expectedTitle to "{title}"\n'
        f"set expectedLeft to {plan['expected_left']}\n"
        f"set expectedTop to {plan['expected_top']}\n"
        f"set expectedWidth to {plan['expected_width']}\n"
        f"set expectedHeight to {plan['expected_height']}\n"
        f'tell application "{process}" to activate\n'
        'tell application "System Events"\n'
        "  set matches to every process whose name is expectedProcess\n"
        '  if (count of matches) is not 1 then error "target window changed before input"\n'
        "  set targetProcess to item 1 of matches\n"
        '  if (count of windows of targetProcess) is not 1 then error "target window changed before input"\n'
        "  set targetWindow to window 1 of targetProcess\n"
        '  if name of targetWindow is not expectedTitle then error "target window changed before input"\n'
        "  set windowPosition to position of targetWindow\n"
        "  set windowSize to size of targetWindow\n"
        '  if item 1 of windowPosition is not expectedLeft then error "target window changed before input"\n'
        '  if item 2 of windowPosition is not expectedTop then error "target window changed before input"\n'
        '  if item 1 of windowSize is not expectedWidth then error "target window changed before input"\n'
        '  if item 2 of windowSize is not expectedHeight then error "target window changed before input"\n'
        f"  {action}\n"
        "end tell\n"
    )
