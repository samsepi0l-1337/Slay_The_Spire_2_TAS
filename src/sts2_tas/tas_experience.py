from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .ml_entities import ActionCandidate
from .tas_movie import TasFrame

BehaviorPolicy = Literal["human", "search", "heuristic", "verified_heuristic", "model_self", "failed_rollout", "no_op", "drift"]
LabelSource = Literal["human", "search_success", "verified_heuristic", "model_self", "failed_rollout", "no_op", "drift", "illegal", "no_terminal"]

DEFAULT_SUPERVISED_LABEL_SOURCES = frozenset({"human", "search_success", "verified_heuristic"})
EXCLUDED_LABEL_SOURCES = frozenset({"model_self", "failed_rollout", "no_op", "drift", "illegal", "no_terminal"})
EXCLUDED_BEHAVIOR_POLICIES = frozenset({"failed_rollout", "no_op", "drift"})


@dataclass(frozen=True)
class TasExperience:
    behavior_policy: BehaviorPolicy
    label_source: LabelSource
    movie_frame: TasFrame
    run_id: str
    state_fingerprint: str
    legal_actions: list[ActionCandidate]
    selected_action: ActionCandidate
    terminal_return: float | None
    changed_ack: bool = False
    no_op: bool = False
    drift_detected: bool = False
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.behavior_policy not in BehaviorPolicy.__args__:  # type: ignore[attr-defined]
            raise ValueError(f"unsupported behavior_policy: {self.behavior_policy}")
        if self.label_source not in LabelSource.__args__:  # type: ignore[attr-defined]
            raise ValueError(f"unsupported label_source: {self.label_source}")
        if not self.run_id:
            raise ValueError("run_id is required")
        if not self.state_fingerprint:
            raise ValueError("state_fingerprint is required")
        if not self.legal_actions:
            raise ValueError("legal_actions is required")
        if not any(action.identity == self.selected_action.identity for action in self.legal_actions):
            raise ValueError("selected_action must be present in legal_actions")

    def is_default_supervised(self) -> bool:
        if self.label_source in EXCLUDED_LABEL_SOURCES:
            return False
        if self.behavior_policy in EXCLUDED_BEHAVIOR_POLICIES:
            return False
        if not self.changed_ack:
            return False
        if self.no_op or self.drift_detected or self.failure_reason is not None:
            return False
        if self.terminal_return is None:
            return False
        if not self.selected_action.legal:
            return False
        return self.label_source in DEFAULT_SUPERVISED_LABEL_SOURCES

    def to_dict(self) -> dict[str, Any]:
        return {
            "behavior_policy": self.behavior_policy,
            "label_source": self.label_source,
            "movie_frame": self.movie_frame.to_dict(),
            "run_id": self.run_id,
            "state_fingerprint": self.state_fingerprint,
            "legal_actions": [asdict(action) for action in self.legal_actions],
            "selected_action": asdict(self.selected_action),
            "terminal_return": self.terminal_return,
            "changed_ack": self.changed_ack,
            "no_op": self.no_op,
            "drift_detected": self.drift_detected,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TasExperience:
        return cls(
            behavior_policy=data["behavior_policy"],
            label_source=data["label_source"],
            movie_frame=TasFrame.from_dict(data["movie_frame"]),
            run_id=str(data["run_id"]),
            state_fingerprint=str(data["state_fingerprint"]),
            legal_actions=[ActionCandidate.from_dict(action) for action in data["legal_actions"]],
            selected_action=ActionCandidate.from_dict(data["selected_action"]),
            terminal_return=(
                None if data["terminal_return"] is None else float(data["terminal_return"])
            ),
            changed_ack=_strict_bool(data.get("changed_ack", False), "changed_ack"),
            no_op=_strict_bool(data.get("no_op", False), "no_op"),
            drift_detected=_strict_bool(data.get("drift_detected", False), "drift_detected"),
            failure_reason=data.get("failure_reason"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> TasExperience:
        return cls.from_dict(json.loads(payload))


def supervised_training_experiences(experiences: Iterable[TasExperience]) -> list[TasExperience]:
    return [experience for experience in experiences if experience.is_default_supervised()]


def load_tas_experiences(path: Path) -> list[TasExperience]:
    return [TasExperience.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_tas_experiences(path: Path, experiences: Iterable[TasExperience]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for experience in experiences:
            file.write(experience.to_json() + "\n")


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value
