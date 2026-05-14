from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schema import GameStep

TransitionStatus = Literal["changed", "no_op", "timeout"]


@dataclass(frozen=True)
class TransitionAcknowledgement:
    action_id: str
    status: TransitionStatus
    attempts: int
    before_signature: str
    after_signature: str | None
    retry_recommended: bool


def acknowledge_transition(
    before: GameStep,
    after_frames: list[GameStep],
    action_id: str,
) -> TransitionAcknowledgement:
    before_signature = _signature(before)
    if not after_frames:
        return TransitionAcknowledgement(
            action_id=action_id,
            status="timeout",
            attempts=0,
            before_signature=before_signature,
            after_signature=None,
            retry_recommended=True,
        )
    for attempt, frame in enumerate(after_frames, start=1):
        after_signature = _signature(frame)
        if after_signature != before_signature:
            return TransitionAcknowledgement(
                action_id=action_id,
                status="changed",
                attempts=attempt,
                before_signature=before_signature,
                after_signature=after_signature,
                retry_recommended=False,
            )
    return TransitionAcknowledgement(
        action_id=action_id,
        status="no_op",
        attempts=len(after_frames),
        before_signature=before_signature,
        after_signature=_signature(after_frames[-1]),
        retry_recommended=True,
    )


def _signature(step: GameStep) -> str:
    legal_actions = ",".join(action.identity for action in step.actions if action.legal)
    player = step.state.player
    return "|".join(
        [
            step.state.decision_context,
            str(step.state.floor),
            str(player.hp),
            str(player.block),
            str(player.energy),
            legal_actions,
        ]
    )
