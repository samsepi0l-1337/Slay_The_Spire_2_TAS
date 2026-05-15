from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts2_tas.tas_hook_ipc import HookIpcEvent, read_hook_jsonl


def _event() -> dict[str, object]:
    return {
        "schema_version": "sts2-hook-canary.v1",
        "event_type": "present_frame",
        "session_nonce": "nonce-1",
        "process_id": 1234,
        "target_pid": 1234,
        "frame_counter": 7,
        "timestamp_utc": "2026-05-15T00:00:00Z",
        "thread_id": 5678,
        "passive_only": True,
        "foreground": True,
        "window": {
            "hwnd": "0xABC",
            "title": "Slay the Spire 2",
            "class_name": "UnityWndClass",
            "process_name": "SlayTheSpire2.exe",
            "client_width": 1920,
            "client_height": 1080,
            "screen_bounds": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        },
        "capture": {
            "mode": "hash_only",
            "frame_hash": "sha256:frame",
            "hash_algorithm": "sha256",
            "screenshot_path": None,
            "width": 1920,
            "height": 1080,
            "format": "DXGI_FORMAT_R8G8B8A8_UNORM",
        },
    }


def test_hook_ipc_event_validates_nonce_pid_and_passive_only() -> None:
    event = HookIpcEvent.from_dict(_event(), expected_nonce="nonce-1", expected_pid=1234)

    assert event.frame_counter == 7
    assert event.frame_hash == "sha256:frame"
    with pytest.raises(ValueError, match="nonce"):
        HookIpcEvent.from_dict(_event(), expected_nonce="bad", expected_pid=1234)
    with pytest.raises(ValueError, match="pid"):
        HookIpcEvent.from_dict(_event(), expected_nonce="nonce-1", expected_pid=999)
    with pytest.raises(ValueError, match="passive-only"):
        HookIpcEvent.from_dict(_event() | {"passive_only": False}, expected_nonce="nonce-1", expected_pid=1234)


def test_read_hook_jsonl_reads_complete_events(tmp_path: Path) -> None:
    path = tmp_path / "hook.jsonl"
    path.write_text(json.dumps(_event(), sort_keys=True) + "\n\n", encoding="utf-8")

    events = read_hook_jsonl(path, expected_nonce="nonce-1", expected_pid=1234)

    assert len(events) == 1
    assert events[0].target_process == "SlayTheSpire2.exe"


def test_hook_ipc_event_rejects_non_contract_events() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        HookIpcEvent.from_dict(_event() | {"schema_version": "bad"}, expected_nonce="nonce-1", expected_pid=1234)
    with pytest.raises(ValueError, match="event_type"):
        HookIpcEvent.from_dict(_event() | {"event_type": "other"}, expected_nonce="nonce-1", expected_pid=1234)
    with pytest.raises(ValueError, match="process_id"):
        HookIpcEvent.from_dict(_event() | {"process_id": 999}, expected_nonce="nonce-1", expected_pid=1234)
    with pytest.raises(ValueError, match="window"):
        payload = _event()
        payload.pop("window")
        HookIpcEvent.from_dict(payload, expected_nonce="nonce-1", expected_pid=1234)
    with pytest.raises(ValueError, match="capture"):
        payload = _event()
        payload.pop("capture")
        HookIpcEvent.from_dict(payload, expected_nonce="nonce-1", expected_pid=1234)
