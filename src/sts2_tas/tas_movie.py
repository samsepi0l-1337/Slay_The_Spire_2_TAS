from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


PhysicalInputKind = Literal["key_tap", "click", "wait"]


@dataclass(frozen=True)
class PhysicalInput:
    index: int
    kind: PhysicalInputKind
    key: str | None = None
    x: int | None = None
    y: int | None = None
    button: str | None = None
    frames: int | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("physical input index must be non-negative")
        if self.kind not in {"key_tap", "click", "wait"}:
            raise ValueError(f"unsupported physical input kind: {self.kind}")
        if self.kind == "key_tap" and not self.key:
            raise ValueError("key_tap physical input requires key")
        if self.kind == "click" and (self.x is None or self.y is None):
            raise ValueError("click physical input requires click coordinates")
        if self.kind == "wait" and (self.frames is None or self.frames <= 0):
            raise ValueError("wait physical input requires positive frames")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"index": self.index, "kind": self.kind}
        if self.key is not None:
            data["key"] = self.key
        if self.x is not None:
            data["x"] = self.x
        if self.y is not None:
            data["y"] = self.y
        if self.button is not None:
            data["button"] = self.button
        if self.frames is not None:
            data["frames"] = self.frames
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalInput:
        return cls(
            index=int(data["index"]),
            kind=data["kind"],
            key=data.get("key"),
            x=_optional_int(data.get("x")),
            y=_optional_int(data.get("y")),
            button=data.get("button"),
            frames=_optional_int(data.get("frames")),
        )

    def to_json(self) -> str:
        return _stable_json(self.to_dict())

    @classmethod
    def from_json(cls, payload: str) -> PhysicalInput:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class TasFrame:
    frame: int
    semantic_action: dict[str, Any] | None
    physical_input: list[PhysicalInput]
    screen_hash: str
    state_fingerprint: str
    decision_context: str
    source_policy: str
    label_source: str
    outcome_ref: str | None = None

    def __post_init__(self) -> None:
        if self.frame < 0:
            raise ValueError("frame index must be non-negative")
        if not self.screen_hash:
            raise ValueError("screen_hash is required")
        if not self.state_fingerprint:
            raise ValueError("state_fingerprint is required")
        if not self.decision_context:
            raise ValueError("decision_context is required")
        if not self.source_policy:
            raise ValueError("source_policy is required")
        if not self.label_source:
            raise ValueError("label_source is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "semantic_action": self.semantic_action,
            "physical_input": [input_state.to_dict() for input_state in self.physical_input],
            "screen_hash": self.screen_hash,
            "state_fingerprint": self.state_fingerprint,
            "decision_context": self.decision_context,
            "source_policy": self.source_policy,
            "label_source": self.label_source,
            "outcome_ref": self.outcome_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TasFrame:
        return cls(
            frame=int(data["frame"]),
            semantic_action=_optional_dict(data.get("semantic_action")),
            physical_input=[PhysicalInput.from_dict(item) for item in data.get("physical_input", [])],
            screen_hash=str(data["screen_hash"]),
            state_fingerprint=str(data["state_fingerprint"]),
            decision_context=str(data["decision_context"]),
            source_policy=str(data["source_policy"]),
            label_source=str(data["label_source"]),
            outcome_ref=data.get("outcome_ref"),
        )

    def to_json(self) -> str:
        return _stable_json(self.to_dict())

    @classmethod
    def from_json(cls, payload: str) -> TasFrame:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class TasMovie:
    run_id: str
    frames: list[TasFrame]
    game_version: str = "unknown"
    branch: str = "unknown"
    target_process: str = "SlayTheSpire2"

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is required")
        for earlier, later in zip(self.frames, self.frames[1:]):
            if later.frame <= earlier.frame:
                raise ValueError("frames must be strictly monotonic increasing")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "game_version": self.game_version,
            "branch": self.branch,
            "target_process": self.target_process,
            "frames": [frame.to_dict() for frame in self.frames],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TasMovie:
        return cls(
            run_id=str(data["run_id"]),
            game_version=str(data.get("game_version", "unknown")),
            branch=str(data.get("branch", "unknown")),
            target_process=str(data.get("target_process", "SlayTheSpire2")),
            frames=[TasFrame.from_dict(frame) for frame in data.get("frames", [])],
        )

    def to_json(self) -> str:
        return _stable_json(self.to_dict())

    @classmethod
    def from_json(cls, payload: str) -> TasMovie:
        return cls.from_dict(json.loads(payload))

    @classmethod
    def load(cls, path: Path) -> TasMovie:
        return cls.from_json(path.read_text(encoding="utf-8"))

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    def prefix_hash(self, frame_count: int | None = None) -> str:
        if frame_count is None:
            frame_count = len(self.frames)
        if frame_count < 0 or frame_count > len(self.frames):
            raise ValueError("frame_count must be in range [0, len(frames)]")
        payload = {
            "run_id": self.run_id,
            "game_version": self.game_version,
            "branch": self.branch,
            "target_process": self.target_process,
            "frames": [frame.to_dict() for frame in self.frames[:frame_count]],
        }
        return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_dict(value: Any) -> dict[str, Any] | None:
    return None if value is None else dict(value)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
