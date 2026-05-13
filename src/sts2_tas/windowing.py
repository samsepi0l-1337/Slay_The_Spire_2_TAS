from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Callable, Protocol

from .schema import TargetWindow, WindowBounds

WindowCommandRunner = Callable[[list[str]], object]


class WindowDetectorProtocol(Protocol):
    def detect(self, process: str) -> TargetWindow:  # pragma: no cover
        ...


@dataclass(frozen=True)
class WindowDetector:
    platform_name: str | None = None
    runner: WindowCommandRunner | None = None

    def detect(self, process: str) -> TargetWindow:
        if (self.platform_name or platform.system()).lower() != "darwin":
            raise RuntimeError("target window detection is only supported on macOS")
        output = self._run(_macos_window_script(process))
        return _parse_detector_output(process, output)

    def _run(self, script: str) -> str:
        runner = self.runner or _run_osascript
        result = runner(["osascript", "-e", script])
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return "" if result is None else str(result)


def _run_osascript(command: list[str]) -> str:
    return subprocess.check_output(command, text=True)


def _macos_window_script(process: str) -> str:
    escaped = process.replace("\\", "\\\\").replace('"', '\\"')
    return (
        'tell application "System Events"\n'
        f'  set matches to every process whose name is "{escaped}"\n'
        "  if (count of matches) is not 1 then return \"\"\n"
        "  set targetProcess to item 1 of matches\n"
        "  if (count of windows of targetProcess) is not 1 then return \"\"\n"
        "  set targetWindow to window 1 of targetProcess\n"
        "  set windowPosition to position of targetWindow\n"
        "  set windowSize to size of targetWindow\n"
        f'  return "{escaped}" & tab & name of targetWindow & tab & item 1 of windowPosition & tab & '
        "item 2 of windowPosition & tab & item 1 of windowSize & tab & item 2 of windowSize\n"
        "end tell"
    )


def _parse_detector_output(process: str, output: str) -> TargetWindow:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"target window not found or ambiguous for process: {process}")
    columns = lines[0].split("\t")
    if len(columns) != 6:
        raise RuntimeError(f"target window output is invalid for process: {process}")
    found_process, title, left, top, width, height = columns
    if found_process != process:
        raise RuntimeError(f"target window process mismatch: {found_process}")
    try:
        bounds = WindowBounds(left=int(left), top=int(top), width=int(width), height=int(height))
    except ValueError as error:
        raise RuntimeError(f"target window bounds are invalid for process: {process}") from error
    return TargetWindow(process=found_process, title=title, bounds=bounds)
