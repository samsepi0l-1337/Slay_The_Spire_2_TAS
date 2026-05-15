# STS2 TAS Hook IPC Contract

SPDX-License-Identifier: MIT

This contract describes the passive-only IPC shape for the future
`sts2_tas_hook` x64 Windows canary. The current repository contains only a
documented scaffold; no actual build, injection, or runtime transport is
required.

## Transport

Preferred transport is UTF-8 JSON Lines over a local named pipe:

```text
\\.\pipe\sts2_tas_hook_canary
```

Each line is one complete event. Writers must flush complete lines only. Readers
must tolerate unknown fields and reject events that are missing required fields.

## Event type: `present_frame`

Required fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Contract version, currently `sts2-hook-canary.v1`. |
| `event_type` | string | Must be `present_frame`. |
| `frame_counter` | integer | Monotonic counter incremented by the Present hook. |
| `timestamp_utc` | string | ISO-8601 UTC timestamp captured without a time hook. |
| `process_id` | integer | Windows process id for the observed process. |
| `thread_id` | integer | Windows thread id that observed Present. |
| `passive_only` | boolean | Must be `true`. |
| `foreground` | boolean | Whether the observed game window is foreground. |
| `window` | object | Foreground/window metadata. |
| `capture` | object | Frame screenshot/hash metadata. |

Window object:

| Field | Type | Description |
| --- | --- | --- |
| `hwnd` | string | Hex HWND value. |
| `title` | string | Window title, if available. |
| `class_name` | string | Win32 class name, if available. |
| `process_name` | string | Process executable name, if available. |
| `client_width` | integer | Client-area width in pixels. |
| `client_height` | integer | Client-area height in pixels. |
| `screen_bounds` | object | `left`, `top`, `right`, `bottom` screen coordinates. |

Capture object:

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `none`, `hash_only`, `file`, or `shared_buffer`. |
| `frame_hash` | string/null | SHA-256 or other declared hash of copied frame bytes. |
| `hash_algorithm` | string/null | Hash algorithm name, for example `sha256`. |
| `screenshot_path` | string/null | File path when `mode` is `file`. |
| `width` | integer/null | Captured frame width. |
| `height` | integer/null | Captured frame height. |
| `format` | string/null | DXGI or encoded image format. |

## Example

```json
{"schema_version":"sts2-hook-canary.v1","event_type":"present_frame","frame_counter":42,"timestamp_utc":"2026-05-15T00:00:00Z","process_id":1234,"thread_id":5678,"passive_only":true,"foreground":true,"window":{"hwnd":"0x00000000000ABC","title":"Slay the Spire 2","class_name":"UnityWndClass","process_name":"SlayTheSpire2.exe","client_width":1920,"client_height":1080,"screen_bounds":{"left":0,"top":0,"right":1920,"bottom":1080}},"capture":{"mode":"hash_only","frame_hash":"sha256:example","hash_algorithm":"sha256","screenshot_path":null,"width":1920,"height":1080,"format":"DXGI_FORMAT_R8G8B8A8_UNORM"}}
```

## Passive-only invariants

The IPC producer must preserve these invariants for every event:

- `passive_only` is always `true`.
- Present hook observation does not send input.
- Present hook observation does not hook or patch time.
- Frame screenshot/hash collection is best-effort and may be skipped rather than
  stalling the game loop.
- Foreground/window metadata collection must not activate, resize, move, or
  otherwise mutate the target window.
