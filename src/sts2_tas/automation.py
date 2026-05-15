from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .ml_entities import resolve_action_identity
from .schema import (
    AutomationAction,
    Box,
    CoordinateSpace,
    GameStep,
    TargetWindow,
    _click_step,
)
from . import tas_input
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


@dataclass
class DeferredJsonlInputController:
    log_path: Path
    events: list[dict[str, object]] = field(default_factory=list)

    def send(self, action: AutomationAction) -> None:
        self.events.append(action.to_event())

    def commit(self) -> None:
        if not self.events:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as file:
            for event in self.events:
                file.write(json.dumps(event, sort_keys=True) + "\n")
        self.events.clear()

    def rollback(self) -> None:
        self.events.clear()


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
    resolved_action_id = resolve_action_identity(step.actions, action_id)
    candidate = next(action for action in step.actions if action.identity == resolved_action_id)
    automation_action = (
        "skip" if candidate.action_type in {"skip_reward", "end_turn", "play_card"} else "pick"
    )
    option_id = (
        candidate.identity
        if candidate.action_type == "play_card"
        else _automation_option_id(candidate, automation_action)
    )
    key = "e" if candidate.action_type == "end_turn" else None
    if candidate.action_type == "play_card":
        key, targets = tas_input.build_play_card_plan(candidate)
        target = None
        if candidate.target_monster_id is not None and candidate.target_screen_box is None:
            raise ValueError(f"action_id has no target screen box: {action_id}")
    else:
        target = candidate.screen_box
        if automation_action == "pick" and target is None:
            raise ValueError(f"action_id has no screen target: {action_id}")
        if automation_action == "pick" and candidate.target_monster_id is not None and candidate.target_screen_box is None:
            raise ValueError(f"action_id has no target screen box: {action_id}")
        targets = _input_targets(candidate, target)
    return AutomationAction(
        action=automation_action,
        option_id=option_id,
        dry_run=dry_run,
        target=target,
        targets=targets,
        key=key,
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


def native_command(action: AutomationAction, platform_name: str) -> list[str]:
    return _native_command(action, platform_name)


def _input_targets(candidate, target: Box | None) -> list[Box] | None:
    if target is None or candidate.target_screen_box is None:
        return None
    return [target, candidate.target_screen_box]


def _automation_option_id(candidate, automation_action: str) -> str | None:
    if candidate.action_type == "end_turn":
        return candidate.identity
    if automation_action == "skip":
        return None
    return candidate.option_id or candidate.identity


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


def _native_input_plan(action: AutomationAction, system: str) -> dict[str, object]:
    if system == "windows" and action.action == "skip" and action.key is None and action.target is None:
        plan = {"kind": "keypress", "key": "escape"}
    elif action.key is not None:
        target_boxes: list[Box] = []
        if action.targets is not None:
            target_boxes = action.targets
        elif action.target is not None:
            target_boxes = [action.target]
        if not target_boxes:
            plan = {"kind": "keypress", "key": action.key}
        else:
            steps = [_click_step(target, action.coordinate_space, action.target_window) for target in target_boxes]
            plan = {"kind": "sequence", "steps": [{"kind": "keypress", "key": action.key}, *steps]}
    else:
        plan = action.input_plan()
    if action.target_window is not None:
        plan["target_process"] = action.target_window.process
        plan["target_title"] = action.target_window.title
        plan["expected_left"] = action.target_window.bounds.left
        plan["expected_top"] = action.target_window.bounds.top
        plan["expected_width"] = action.target_window.bounds.width
        plan["expected_height"] = action.target_window.bounds.height
    return plan


def _macos_command(plan: dict[str, object]) -> list[str]:
    target_process = plan.get("target_process")
    action = _macos_action(plan)
    if isinstance(target_process, str):
        return ["osascript", "-e", _macos_target_guard(plan, action)]
    if plan["kind"] == "sequence":
        return ["osascript", "-e", f'tell application "System Events"\n{_indent_applescript(action)}\nend tell']
    return ["osascript", "-e", f'tell application "System Events" to {action}']


def _linux_command(plan: dict[str, object]) -> list[str]:
    if plan["kind"] == "sequence":
        command = ["xdotool"]
        for step in plan["steps"]:
            command.extend(_linux_step_args(step))
        return command
    return ["xdotool", *_linux_step_args(plan)]


def _linux_step_args(plan: dict[str, object]) -> list[str]:
    if plan["kind"] == "click":
        return ["mousemove", str(plan["x"]), str(plan["y"]), "click", "1"]
    return ["key", str(plan["key"])]


def _windows_command(plan: dict[str, object]) -> list[str]:
    if "target_process" in plan:
        return ["powershell", "-NoProfile", "-Command", _windows_target_guard_script(plan)]
    if plan["kind"] == "click":
        return ["powershell", "-NoProfile", "-Command", _windows_click_script(int(plan["x"]), int(plan["y"]))]
    if plan["kind"] == "sequence":
        return ["powershell", "-NoProfile", "-Command", _windows_sequence_script(plan)]
    return [
        "powershell",
        "-NoProfile",
        "-Command",
        _windows_keypress_command(str(plan["key"])),
    ]


def _windows_click_script(x: int, y: int) -> str:
    return _windows_win32_signature() + _windows_click_action_script(x, y)


def _windows_target_guard_script(plan: dict[str, object]) -> str:
    process = _escape_powershell_single_quoted(str(plan["target_process"]))
    title = _escape_powershell_single_quoted(str(plan["target_title"]))
    action = _windows_action_script(plan)
    return (
        _windows_win32_signature()
        + f"$expectedProcess = '{process}'\n"
        + f"$expectedTitle = '{title}'\n"
        + f"$expectedLeft = {plan['expected_left']}\n"
        + f"$expectedTop = {plan['expected_top']}\n"
        + f"$expectedWidth = {plan['expected_width']}\n"
        + f"$expectedHeight = {plan['expected_height']}\n"
        + "$matches = @(Get-Process | Where-Object { "
        + "$_.ProcessName -eq $expectedProcess -or $_.Name -eq $expectedProcess -or "
        + "$_.MainWindowTitle -eq $expectedProcess })\n"
        + "$windows = @()\n"
        + "foreach ($process in $matches) {\n"
        + "  foreach ($window in [Win32Input]::EnumerateProcessWindows([int]$process.Id)) {\n"
        + "    if ($window.Title -eq $expectedTitle) { $windows += $window }\n"
        + "  }\n"
        + "}\n"
        + "if ($windows.Count -ne 1) { throw 'target window changed before input' }\n"
        + "$targetWindow = $windows[0]\n"
        + "$rect = New-Object Win32Input+RECT\n"
        + "if (-not [Win32Input]::GetWindowRect($targetWindow.Handle, [ref]$rect)) { "
        + "throw 'target window changed before input' }\n"
        + "$width = $rect.Right - $rect.Left\n"
        + "$height = $rect.Bottom - $rect.Top\n"
        + "if ($rect.Left -ne $expectedLeft -or $rect.Top -ne $expectedTop -or "
        + "$width -ne $expectedWidth -or $height -ne $expectedHeight) { "
        + "throw 'target window changed before input' }\n"
        + "if (-not [Win32Input]::SetForegroundWindow($targetWindow.Handle)) { "
        + "throw 'target window changed before input' }\n"
        + action
    )


def _windows_win32_signature() -> str:
    return (
        "$signature = @'\n"
        "using System;\n"
        "using System.Collections.Generic;\n"
        "using System.Runtime.InteropServices;\n"
        "using System.Text;\n"
        "public static class Win32Input {\n"
        "  [StructLayout(LayoutKind.Sequential)] public struct RECT {\n"
        "    public int Left; public int Top; public int Right; public int Bottom;\n"
        "  }\n"
        "  public sealed class WindowInfo {\n"
        "    public IntPtr Handle; public string Title; public int Left; public int Top; public int Width; public int Height;\n"
        "  }\n"
        "  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);\n"
        "  [DllImport(\"user32.dll\")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool IsWindowVisible(IntPtr hWnd);\n"
        "  [DllImport(\"user32.dll\")] public static extern int GetWindowTextLength(IntPtr hWnd);\n"
        "  [DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y);\n"
        "  [DllImport(\"user32.dll\")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);\n"
        "  public static string GetTitle(IntPtr hWnd) {\n"
        "    int length = GetWindowTextLength(hWnd);\n"
        "    StringBuilder builder = new StringBuilder(length + 1);\n"
        "    GetWindowText(hWnd, builder, builder.Capacity);\n"
        "    return builder.ToString();\n"
        "  }\n"
        "  public static WindowInfo[] EnumerateProcessWindows(int processId) {\n"
        "    List<WindowInfo> windows = new List<WindowInfo>();\n"
        "    EnumWindows(delegate (IntPtr hWnd, IntPtr lParam) {\n"
        "      if (!IsWindowVisible(hWnd)) { return true; }\n"
        "      uint ownerProcessId;\n"
        "      GetWindowThreadProcessId(hWnd, out ownerProcessId);\n"
        "      if (ownerProcessId != processId) { return true; }\n"
        "      RECT rect;\n"
        "      if (!GetWindowRect(hWnd, out rect)) { return true; }\n"
        "      int width = rect.Right - rect.Left;\n"
        "      int height = rect.Bottom - rect.Top;\n"
        "      if (width <= 0 || height <= 0) { return true; }\n"
        "      windows.Add(new WindowInfo { Handle = hWnd, Title = GetTitle(hWnd), Left = rect.Left, Top = rect.Top, Width = width, Height = height });\n"
        "      return true;\n"
        "    }, IntPtr.Zero);\n"
        "    return windows.ToArray();\n"
        "  }\n"
        "}\n"
        "'@\n"
        "Add-Type -TypeDefinition $signature\n"
    )


def _windows_click_action_script(x: int, y: int) -> str:
    return (
        f"if (-not [Win32Input]::SetCursorPos({x}, {y})) {{ throw 'SetCursorPos failed' }}\n"
        "[Win32Input]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)\n"
        "Start-Sleep -Milliseconds 50\n"
        "[Win32Input]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)\n"
    )


def _windows_sequence_script(plan: dict[str, object]) -> str:
    return _windows_win32_signature() + _windows_action_script(plan)


def _windows_action_script(plan: dict[str, object]) -> str:
    if plan["kind"] == "click":
        return _windows_click_action_script(int(plan["x"]), int(plan["y"]))
    if plan["kind"] == "sequence":
        return "".join(_windows_action_script(step) for step in plan["steps"])  # type: ignore[arg-type]
    return _windows_keypress_action_script(str(plan["key"]))


def _windows_keypress_command(key: str) -> str:
    return f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{_windows_key(key)}')"


def _windows_keypress_action_script(key: str) -> str:
    return f"Add-Type -AssemblyName System.Windows.Forms\n[System.Windows.Forms.SendKeys]::SendWait('{_windows_key(key)}')\n"


def _windows_key(key: str) -> str:
    if key.casefold() == "escape":
        return "{ESC}"
    return key.replace("'", "''")


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_powershell_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def _validate_target_window(coordinate_space: CoordinateSpace, target_window: TargetWindow | None) -> None:
    if coordinate_space == "window_relative" and target_window is None:
        raise ValueError("window_relative actions require a current target window")
    if target_window is not None and coordinate_space != "window_relative":
        raise ValueError("target-process coordinate translation requires a window_relative step")


def _macos_target_guard(plan: dict[str, object], action: str) -> str:
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
        "  set targetWindow to missing value\n"
        "  repeat with w in (every window of targetProcess)\n"
        "    set windowPosition to position of w\n"
        "    set windowSize to size of w\n"
        "    if (item 1 of windowPosition) is expectedLeft and (item 2 of windowPosition) is expectedTop and "
        "(item 1 of windowSize) is expectedWidth and (item 2 of windowSize) is expectedHeight then\n"
        "      set targetWindow to w\n"
        "      exit repeat\n"
        "    end if\n"
        "  end repeat\n"
        '  if targetWindow is missing value then error "target window changed before input"\n'
        "  if (length of expectedTitle) is greater than 0 then\n"
        '    if name of targetWindow is not expectedTitle then error "target window changed before input"\n'
        "  end if\n"
        f"{_indent_applescript(action)}\n"
        "end tell\n"
    )


def _macos_action(plan: dict[str, object]) -> str:
    if plan["kind"] == "click":
        return f'click at {{{plan["x"]}, {plan["y"]}}}'
    if plan["kind"] == "sequence":
        return "\n".join(_macos_action(step) for step in plan["steps"])  # type: ignore[arg-type]
    if str(plan["key"]).casefold() == "escape":
        return "key code 53"
    return f'keystroke "{_escape_applescript(str(plan["key"]))}"'


def _indent_applescript(script: str) -> str:
    return "\n".join(f"  {line}" for line in script.splitlines())
