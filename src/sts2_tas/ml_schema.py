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

    @classmethod
    def from_legacy_snapshot(cls, snapshot: Any, catalog_version: str) -> GameStep:
        actions = [_action_from_legacy_option(option) for option in snapshot.options]
        return cls(
            state=StructuredGameState(
                game_version=snapshot.game_version,
                branch=snapshot.branch,
                catalog_version=catalog_version,
                character=snapshot.character,
                ascension=snapshot.ascension,
                floor=snapshot.floor,
                decision_context=_legacy_decision_context(snapshot.options),
                player=PlayerState(hp=snapshot.hp, max_hp=max(snapshot.hp, 1), block=0, energy=0, turn=0),
                cards=[
                    CardInstance(
                        instance_id=f"deck-{index}-{card_id}",
                        card_id=card_id,
                        zone="deck",
                        upgraded=False,
                        base_cost=None,
                        current_cost=None,
                        type="unknown",
                        rarity="unknown",
                        tags=[],
                    )
                    for index, card_id in enumerate(snapshot.deck)
                ],
                relics=[
                    RelicState(relic_id=relic_id, obtained_order=index)
                    for index, relic_id in enumerate(snapshot.relics)
                ],
            ),
            actions=actions,
            chosen_action_id=_legacy_chosen_action_id(snapshot, actions),
            outcome=None,
            observation=ObservationQuality(
                source_type="legacy",
                ocr_confidence=1.0,
                missing_fields=[],
                unknown_tokens=[],
                game_version=snapshot.game_version,
                branch=snapshot.branch,
                catalog_version=catalog_version,
            ),
            screenshot_path=snapshot.screenshot_path,
        )


def _legacy_decision_context(options: list[Any]) -> str:
    if any(option.kind == "card" for option in options):
        return "card_reward"
    if any(option.kind == "relic" for option in options):
        return "relic_reward"
    return "unknown"


def _action_from_legacy_option(option: Any) -> ActionCandidate:
    if option.kind == "skip":
        return ActionCandidate(action_type="skip_reward", option_id=option.id, legal=True)
    return ActionCandidate(action_type=f"pick_{option.kind}", option_id=option.id, legal=True)


def _legacy_chosen_action_id(snapshot: Any, actions: list[ActionCandidate]) -> str | None:
    if snapshot.chosen is None:
        return None
    if snapshot.chosen.action == "pick":
        return snapshot.chosen.option_id
    skip = next((action for action in actions if action.action_type == "skip_reward"), None)
    return skip.identity if skip is not None else "skip"
