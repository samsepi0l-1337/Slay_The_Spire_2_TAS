from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HookIpcEvent:
    session_nonce: str
    target_pid: int
    target_process: str
    frame_counter: int
    frame_hash: str | None
    passive_only: bool
    target_window: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_nonce": self.session_nonce,
            "target_pid": self.target_pid,
            "target_process": self.target_process,
            "frame_counter": self.frame_counter,
            "frame_hash": self.frame_hash,
            "passive_only": self.passive_only,
            "target_window": dict(self.target_window),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, expected_nonce: str, expected_pid: int) -> "HookIpcEvent":
        if payload.get("session_nonce") != expected_nonce:
            raise ValueError("hook IPC session nonce mismatch")
        if int(payload.get("target_pid", -1)) != expected_pid:
            raise ValueError("hook IPC target pid mismatch")
        if payload.get("passive_only") is not True:
            raise ValueError("hook IPC event must be passive-only")
        capture = dict(payload.get("capture", {}))
        target_window = dict(payload.get("target_window") or payload.get("window") or {})
        return cls(
            session_nonce=str(payload["session_nonce"]),
            target_pid=int(payload["target_pid"]),
            target_process=str(payload.get("target_process") or target_window.get("process_name")),
            frame_counter=int(payload["frame_counter"]),
            frame_hash=payload.get("frame_hash") or capture.get("frame_hash"),
            passive_only=True,
            target_window=target_window,
        )


def read_hook_jsonl(path: Path, *, expected_nonce: str, expected_pid: int) -> list[HookIpcEvent]:
    events: list[HookIpcEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(HookIpcEvent.from_dict(json.loads(line), expected_nonce=expected_nonce, expected_pid=expected_pid))
    return events
