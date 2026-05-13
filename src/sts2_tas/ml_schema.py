from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .ml_entities import (
    ActionCandidate,
    CardInstance,
    MonsterState,
    ObservationQuality,
    PathCandidate,
    PlayerState,
    PotionState,
    RelicState,
    StepOutcome,
    StructuredGameState,
)


@dataclass(frozen=True)
class GameStep:
    state: StructuredGameState
    actions: list[ActionCandidate]
    chosen_action_id: str | None
    outcome: StepOutcome | None
    observation: ObservationQuality
    screenshot_path: Path

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError("game steps require at least one action candidate")
        if not any(action.legal for action in self.actions):
            raise ValueError("game steps require at least one legal action candidate")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "actions": [asdict(action) for action in self.actions],
            "chosen_action_id": self.chosen_action_id,
            "outcome": asdict(self.outcome) if self.outcome is not None else None,
            "observation": self.observation.to_dict(),
            "screenshot_path": str(self.screenshot_path),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameStep:
        outcome = data.get("outcome")
        return cls(
            state=StructuredGameState.from_dict(data["state"]),
            actions=[ActionCandidate.from_dict(action) for action in data["actions"]],
            chosen_action_id=data.get("chosen_action_id"),
            outcome=StepOutcome.from_dict(outcome) if outcome is not None else None,
            observation=ObservationQuality.from_dict(data["observation"]),
            screenshot_path=Path(data["screenshot_path"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> GameStep:
        return cls.from_dict(json.loads(payload))
