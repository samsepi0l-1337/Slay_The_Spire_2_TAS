from __future__ import annotations

import re

from .ml_entities import ActionCandidate
from .schema import AutomationAction

_HAND_CARD_ID = re.compile(r"^hand-(\d+)-")


def play_card_slot_to_digit(source_card_id: str) -> int:
    match = _HAND_CARD_ID.match(source_card_id)
    if match is None:
        raise ValueError(f"cannot parse hand slot from action source_card_id: {source_card_id}")
    slot_text = match.group(1)
    if len(slot_text) > 1 and slot_text.startswith("0"):
        raise ValueError(f"cannot parse hand slot from action source_card_id: {source_card_id}")
    return int(slot_text)


def play_card_slot_key(source_card_id: str) -> str:
    slot = play_card_slot_to_digit(source_card_id)
    if slot < 0 or slot > 9:
        raise ValueError(f"hand slot out of supported range: {slot}")
    return "0" if slot == 9 else str(slot + 1)


def build_play_card_plan(candidate: ActionCandidate) -> tuple[str, list[tuple[int, int, int, int]] | None]:
    if candidate.action_type != "play_card":
        raise ValueError("only play_card actions can be mapped to combat key press plans")
    if candidate.source_card_id is None:
        raise ValueError("play_card action requires source_card_id")

    key = play_card_slot_key(candidate.source_card_id)
    if candidate.target_monster_id is None:
        return key, None
    if candidate.target_screen_box is None:
        raise ValueError("play_card action has no target screen box")
    return key, [candidate.target_screen_box]


def build_dry_run_command(action: AutomationAction, platform_name: str = "Windows") -> list[str]:
    from .automation import native_command

    return native_command(action, platform_name)
