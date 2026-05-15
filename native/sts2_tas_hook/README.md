# STS2 TAS Hook Canary

SPDX-License-Identifier: MIT

This directory is a documentation-first scaffold for a future x64 Windows
passive-only hook canary. It is not wired into the Python package, CI does not
build it, and it must not be injected into a live game from this repository
state.

## Scope

- Target: x64 Windows only.
- Technique: Microsoft Detours hook for the Present hook on the D3D/DXGI swap chain.
- Runtime mode: passive-only canary.
- Output: frame counter, foreground window metadata, and optional frame
  screenshot/hash evidence.
- Non-goal: input automation, simulation speed changes, RNG hooks, or game
  state mutation.

## Passive-only policy

The hook may observe frames after `Present` is called and may copy metadata or a
frame image into a local IPC payload. The hook must never call input APIs, never
patch time APIs, never block the game loop for analysis, and never modify game
memory.

Explicitly forbidden operations:

- no input hook: no `SendInput`, mouse, keyboard, controller, window activation, or
  focus stealing.
- no time hook: no `QueryPerformanceCounter`, `GetTickCount`, sleep, timer, or
  frame pacing interception.
- no gameplay mutation: no memory writes, command injection, save edits, or RNG
  hooks.
- no network side effects from the hook DLL.

## Proposed files

- `CMakeLists.txt`: x64 Windows DLL scaffold, optional Detours discovery, and
  passive-only compile definitions.
- `sts2_tas_hook.cpp`: dummy exported canary surface with placeholders for a
  Detours `Present` hook, frame counter, foreground/window metadata, and frame
  screenshot/hash collection.
- `ipc_contract.md`: JSON Lines IPC schema for the passive canary events.
- `README.md`: policy and integration notes.

## Event model

The canary emits one event per observed frame. A future implementation should
send JSON Lines through a named pipe or shared-memory ring buffer owned by the
Python controller. Event fields are documented in `ipc_contract.md`.

Required evidence per frame:

- `frame_counter`: monotonic unsigned frame counter incremented from Present.
- `timestamp_utc`: wall-clock event timestamp captured outside any time hook.
- `process_id` and `thread_id`.
- `foreground`: whether the game window is foreground at observation time.
- `window`: HWND value, title, class name, process name, client size, and
  screen bounds.
- `frame_hash`: content hash when screenshot capture is enabled.
- `screenshot`: optional path or shared-buffer metadata for the copied frame.

## Detours integration notes

The real implementation should attach Detours only after the swap chain
function pointer is resolved in a Windows x64 process. The detour body should
call the original Present first or last according to the measured capture path,
but it must remain passive-only either way. Any GPU readback should use bounded,
non-blocking staging resources or skip capture when the frame is not available
without stalling.

The current `sts2_tas_hook.cpp` keeps all capture operations as placeholders so
hidden tests can verify the contract without depending on a Windows SDK,
Detours, or a game process.

## Safety checklist

- Build is x64 Windows only.
- Hook is Detours based and scoped to Present.
- Frame counter is monotonic.
- Foreground/window metadata is collected without changing focus.
- Frame screenshot/hash collection is optional and best-effort.
- Passive-only/no input/no time hook policy is documented in code and README.
- No actual build, injection, or execution is required for this scaffold.
