from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReinforcementLearningExtensionPlan:
    algorithm: str
    status: str
    prerequisites: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]


PPO_EXTENSION_PLAN = ReinforcementLearningExtensionPlan(
    algorithm="PPO",
    status="planned",
    prerequisites=(
        "stable simulator environment",
        "large parallel rollout collection",
        "seed-loop outcome logging",
        "combat action candidate generation",
    ),
    explicit_exclusions=(
        "no PPO optimizer in v1",
        "no GNN map encoder in v1",
        "no simulator-backed self-play in v1",
    ),
)


def ppo_is_available() -> bool:
    return False
