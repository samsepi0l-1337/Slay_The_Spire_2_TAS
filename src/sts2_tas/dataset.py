from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TransitionRecord:
    state_json: dict[str, Any]
    valid_actions_json: list[dict[str, Any]]
    chosen_action_json: dict[str, Any]
    reward: float
    terminal: bool
    result: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    game_version: str | None = None
    mod_version: str | None = None
    seed: str | None = None
    timestamp: float | None = None
    floor: int | None = None
    phase: str | None = None
    screenshot_path: str | None = None
    policy_id: str | None = None
    latency_ms: float | None = None
    failure_reason: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class JsonlTransitionWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: TransitionRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json() + "\n")

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]
