from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from .ml_schema import ALLOWED_LABEL_SOURCES, ActionCandidate, GameStep, LabelSource

SUPERVISED_LABEL_SOURCES = {"human", "search", "heuristic"}


@dataclass(frozen=True)
class EpisodeState:
    run_id: str
    seed: int
    game_version: str
    floor: int
    room_type: str
    turn_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EpisodeState:
        return cls(
            run_id=str(data["run_id"]),
            seed=int(data["seed"]),
            game_version=str(data["game_version"]),
            floor=int(data["floor"]),
            room_type=str(data["room_type"]),
            turn_index=int(data["turn_index"]),
        )


@dataclass(frozen=True)
class TrajectoryStep:
    run_id: str
    seed: int
    game_version: str
    floor: int
    room_type: str
    turn_index: int
    state_before: EpisodeState
    legal_actions: list[ActionCandidate]
    selected_action: ActionCandidate
    state_after: EpisodeState
    reward: float
    terminal: bool
    label_source: LabelSource = "human"

    def __post_init__(self) -> None:
        if self.label_source not in ALLOWED_LABEL_SOURCES:
            raise ValueError(f"unsupported label_source: {self.label_source}")
        if not self.legal_actions:
            raise ValueError("trajectory steps require legal_actions")
        if not any(action.identity == self.selected_action.identity for action in self.legal_actions):
            raise ValueError("selected_action must be present in legal_actions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "game_version": self.game_version,
            "floor": self.floor,
            "room_type": self.room_type,
            "turn_index": self.turn_index,
            "state_before": self.state_before.to_dict(),
            "legal_actions": [asdict(action) for action in self.legal_actions],
            "selected_action": asdict(self.selected_action),
            "state_after": self.state_after.to_dict(),
            "reward": self.reward,
            "terminal": self.terminal,
            "label_source": self.label_source,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryStep:
        return cls(
            run_id=str(data["run_id"]),
            seed=int(data["seed"]),
            game_version=str(data["game_version"]),
            floor=int(data["floor"]),
            room_type=str(data["room_type"]),
            turn_index=int(data["turn_index"]),
            state_before=EpisodeState.from_dict(data["state_before"]),
            legal_actions=[ActionCandidate.from_dict(action) for action in data["legal_actions"]],
            selected_action=ActionCandidate.from_dict(data["selected_action"]),
            state_after=EpisodeState.from_dict(data["state_after"]),
            reward=float(data["reward"]),
            terminal=bool(data["terminal"]),
            label_source=data.get("label_source", "human"),
        )

    @classmethod
    def from_json(cls, payload: str) -> TrajectoryStep:
        return cls.from_dict(json.loads(payload))


def load_trajectory_steps(path: Path) -> list[TrajectoryStep]:
    return [TrajectoryStep.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_trajectory_steps(path: Path, steps: Iterable[TrajectoryStep]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for step in steps:
            file.write(step.to_json() + "\n")


def supervised_training_steps(steps: Iterable[GameStep]) -> list[GameStep]:
    return [step for step in steps if step.chosen_action_id is not None and step.label_source in SUPERVISED_LABEL_SOURCES]


def value_target_for_step(step: GameStep) -> float:
    if step.outcome is None:
        return 0.0
    outcome = step.outcome
    if outcome.value_target is not None:
        return float(outcome.value_target)
    if outcome.discounted_return is not None:
        return float(outcome.discounted_return)
    if outcome.immediate_reward != 0.0 or outcome.floor_reached > 0 or outcome.hp_remaining > 0 or outcome.terminal:
        shaped = outcome.immediate_reward + min(outcome.floor_reached, 60) / 60.0 + max(outcome.hp_remaining, 0) / 100.0
        if outcome.terminal and outcome.victory:
            shaped += 0.25
        return max(0.0, min(1.0, shaped))
    return 1.0 if outcome.victory else 0.0
