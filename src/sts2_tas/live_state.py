from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .schema import Box, OcrResult


@dataclass(frozen=True)
class LiveStateExtraction:
    state_payload: dict[str, Any]
    state_boxes: dict[str, Box]
    floor: int | None
    missing_fields: list[str]
    unknown_tokens: list[str]


_HP_RE = re.compile(r"\bhp\s+(?P<hp>\d+)\s*/\s*(?P<max_hp>\d+)\b", re.IGNORECASE)
_ENERGY_RE = re.compile(r"\benergy\s+(?P<energy>\d+)(?:\s*/\s*\d+)?\b", re.IGNORECASE)
_BLOCK_RE = re.compile(r"\bblock\s+(?P<block>\d+)\b", re.IGNORECASE)
_GOLD_RE = re.compile(r"\bgold\s+(?P<gold>\d+)\b", re.IGNORECASE)
_FLOOR_RE = re.compile(r"\bfloor\s+(?P<floor>\d+)\b", re.IGNORECASE)
_TURN_RE = re.compile(r"\bturn\s+(?P<turn>\d+)\b", re.IGNORECASE)
_HAND_RE = re.compile(
    r"^hand\s+(?P<name>[a-zA-Z_ -]+?)(?:\s+cost\s+(?P<cost>\d+))?(?:\s+(?P<kind>attack|skill|power|curse|status))?$",
    re.IGNORECASE,
)
_MONSTER_RE = re.compile(
    r"^monster\s+(?P<name>.+?)\s+(?P<hp>\d+)\s*/\s*(?P<max_hp>\d+)"
    r"(?:\s+block\s+(?P<block>\d+))?"
    r"(?:\s+(?P<intent>attack|buff|defend|debuff|unknown)(?:\s+(?P<damage>\d+)(?:x(?P<hits>\d+))?)?)?$",
    re.IGNORECASE,
)
_PATH_RE = re.compile(
    r"^path\s+(?P<node_id>\S+)\s+(?P<node_type>\S+)\s+depth\s+(?P<depth>\d+)\s+"
    r"elites\s+(?P<elites>\d+)\s+rests\s+(?P<rests>\d+)\s+shops\s+(?P<shops>\d+)\s+"
    r"events\s+(?P<events>\d+)\s+boss\s+(?P<boss>\d+)(?:\s+(?P<forced>forced))?$",
    re.IGNORECASE,
)
_POTION_RE = re.compile(
    r"^potion\s+(?P<potion_id>\S+)\s+slot\s+(?P<slot>\d+)(?:\s+(?P<target>target))?(?:\s+(?P<used>used))?$",
    re.IGNORECASE,
)
_CARD_TYPES = {"strike": "attack", "bash": "attack", "defend": "skill"}
_KNOWN_SCREEN_TEXTS = {
    "bash",
    "burning blood",
    "defend",
    "game over",
    "ironclad",
    "new run",
    "single player",
    "skip",
    "standard",
    "strike",
    "tiny house",
    "victory",
    "victory!",
    "강타",
    "넘기기",
    "수비",
    "아이언클래드",
    "작은 집",
    "타격",
    "타오르는 피",
}
_MIN_STATE_CONFIDENCE = 0.60


def extract_live_state(tokens: list[OcrResult]) -> LiveStateExtraction:
    player: dict[str, Any] = {}
    resources: dict[str, int] = {}
    cards: list[dict[str, Any]] = []
    monsters: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    potions: list[dict[str, Any]] = []
    boxes: dict[str, Box] = {}
    floor: int | None = None
    consumed: set[int] = set()

    for index, token in enumerate(tokens):
        if token.confidence < _MIN_STATE_CONFIDENCE:
            continue
        text = " ".join(token.text.strip().split())
        lower = text.casefold()
        if card := _card_from_text(text, len(cards)):
            cards.append(card)
            boxes[f"card:{card['instance_id']}"] = token.box
            consumed.add(index)
            continue
        if monster := _monster_from_text(text, len(monsters)):
            monsters.append(monster)
            boxes[f"monster:{monster['monster_id']}:{monster['slot_index']}"] = token.box
            consumed.add(index)
            continue
        if path := _path_from_text(text):
            paths.append(path)
            boxes[f"path:{path['node_id']}"] = token.box
            consumed.add(index)
            continue
        if potion := _potion_from_text(text):
            potions.append(potion)
            boxes[f"potion:{potion['potion_id']}:{potion['slot']}"] = token.box
            consumed.add(index)
            continue
        consumed_by_scalar = _extract_player_values(lower, player, resources)
        if floor_match := _FLOOR_RE.search(lower):
            floor = int(floor_match.group("floor"))
            consumed_by_scalar = True
        if consumed_by_scalar:
            consumed.add(index)

    if resources:
        player["character_resource"] = resources
    payload: dict[str, Any] = {}
    if player:
        payload["player"] = player
    if cards:
        payload["cards"] = cards
    if monsters:
        payload["monsters"] = monsters
    if paths:
        payload["path_candidates"] = paths
    if potions:
        payload["potions"] = potions
    if floor is not None:
        payload["_meta"] = {"floor": floor}

    return LiveStateExtraction(
        state_payload=payload,
        state_boxes=boxes,
        floor=floor,
        missing_fields=_missing_fields(payload),
        unknown_tokens=_unknown_tokens(tokens, consumed),
    )


def _extract_player_values(text: str, player: dict[str, Any], resources: dict[str, int]) -> bool:
    consumed = False
    if hp_match := _HP_RE.search(text):
        player["hp"] = int(hp_match.group("hp"))
        player["max_hp"] = int(hp_match.group("max_hp"))
        consumed = True
    for regex, key in ((_ENERGY_RE, "energy"), (_BLOCK_RE, "block"), (_TURN_RE, "turn")):
        if match := regex.search(text):
            player[key] = int(match.group(key))
            consumed = True
    if gold_match := _GOLD_RE.search(text):
        resources["gold"] = int(gold_match.group("gold"))
        consumed = True
    return consumed


def _card_from_text(text: str, index: int) -> dict[str, Any] | None:
    match = _HAND_RE.match(text)
    if match is None:
        return None
    card_id = _slug(match.group("name"))
    card_type = (match.group("kind") or _CARD_TYPES.get(card_id) or "unknown").casefold()
    cost = int(match.group("cost")) if match.group("cost") is not None else None
    tags = [] if card_type == "unknown" else [card_type]
    return {
        "instance_id": f"hand-{index}-{card_id}",
        "card_id": card_id,
        "zone": "hand",
        "upgraded": False,
        "base_cost": cost,
        "current_cost": cost,
        "type": card_type,
        "rarity": "unknown",
        "tags": tags,
    }


def _monster_from_text(text: str, slot_index: int) -> dict[str, Any] | None:
    match = _MONSTER_RE.match(text)
    if match is None:
        return None
    return {
        "monster_id": _slug(match.group("name")),
        "slot_index": slot_index,
        "hp": int(match.group("hp")),
        "max_hp": int(match.group("max_hp")),
        "block": int(match.group("block") or 0),
        "intent_type": (match.group("intent") or "unknown").casefold(),
        "intent_damage": int(match.group("damage") or 0),
        "hit_count": int(match.group("hits") or 1),
        "buffs": [],
        "debuffs": [],
    }


def _path_from_text(text: str) -> dict[str, Any] | None:
    match = _PATH_RE.match(text)
    if match is None:
        return None
    return {
        "node_id": match.group("node_id"),
        "node_type": match.group("node_type").casefold(),
        "depth": int(match.group("depth")),
        "elite_count_ahead": int(match.group("elites")),
        "rest_count_ahead": int(match.group("rests")),
        "shop_count_ahead": int(match.group("shops")),
        "event_count_ahead": int(match.group("events")),
        "boss_distance": int(match.group("boss")),
        "forced_elite": match.group("forced") is not None,
    }


def _potion_from_text(text: str) -> dict[str, Any] | None:
    match = _POTION_RE.match(text)
    if match is None:
        return None
    return {
        "potion_id": _slug(match.group("potion_id")),
        "slot": int(match.group("slot")),
        "requires_target": match.group("target") is not None,
        "usable": match.group("used") is None,
    }


def _missing_fields(payload: dict[str, Any]) -> list[str]:
    missing = []
    player = payload.get("player", {})
    for field in ("hp", "max_hp", "block", "energy", "turn"):
        if field not in player:
            missing.append(f"player.{field}")
    if "character_resource" not in player or "gold" not in player.get("character_resource", {}):
        missing.append("player.character_resource.gold")
    for field in ("cards", "monsters", "path_candidates", "potions"):
        if field not in payload:
            missing.append(field)
    return missing


def _unknown_tokens(tokens: list[OcrResult], consumed: set[int]) -> list[str]:
    return [
        token.text
        for index, token in enumerate(tokens)
        if index not in consumed and token.confidence >= _MIN_STATE_CONFIDENCE and _normalize(token.text) not in _KNOWN_SCREEN_TEXTS
    ]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())
