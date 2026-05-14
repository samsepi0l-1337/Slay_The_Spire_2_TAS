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
        system = (self.platform_name or platform.system()).lower()
        if system == "darwin":
            output = self._run(["osascript", "-e", _macos_window_script(process)])
        elif system == "windows":
            output = self._run(["powershell", "-NoProfile", "-Command", _windows_window_script(process)])
        else:
            raise RuntimeError("target window detection is only supported on macOS or Windows")
        return _parse_detector_output(process, output)

    def _run(self, command: list[str]) -> str:
        runner = self.runner or _run_command
        result = runner(command)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return "" if result is None else str(result)


def _run_command(command: list[str]) -> str:
    return subprocess.check_output(command, text=True)


def _run_osascript(command: list[str]) -> str:
    return _run_command(command)


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


def _windows_window_script(process: str) -> str:
    escaped = process.replace("'", "''")
    return (
        "$signature = @'\n"
        "using System;\n"
        "using System.Collections.Generic;\n"
        "using System.Runtime.InteropServices;\n"
        "using System.Text;\n"
        "public static class Win32Window {\n"
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
        f"$query = '{escaped}'\n"
        "$matches = @(Get-Process | Where-Object { $_.ProcessName -eq $query -or $_.Name -eq $query -or $_.MainWindowTitle -eq $query })\n"
        "$windows = @()\n"
        "foreach ($process in $matches) {\n"
        "  foreach ($window in [Win32Window]::EnumerateProcessWindows([int]$process.Id)) {\n"
        "    $windows += $window\n"
        "  }\n"
        "}\n"
        "if ($windows.Count -ne 1) { return }\n"
        "$targetWindow = $windows[0]\n"
        "[Console]::Out.WriteLine(($query, $targetWindow.Title, $targetWindow.Left, $targetWindow.Top, $targetWindow.Width, $targetWindow.Height) -join \"`t\")\n"
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
