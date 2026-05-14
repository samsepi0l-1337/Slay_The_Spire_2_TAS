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
    field_confidence: dict[str, float]


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
_SHOP_ITEM_RE = re.compile(
    r"^shop\s+item\s+(?P<label>.+?)\s+(?P<kind>card|relic|potion|remove)\s+price\s+(?P<price>\d+)"
    r"(?:\s+card\s+(?P<card_id>\S+))?(?:\s+target\s+(?P<removal_target>\S+))?(?:\s+(?P<sold>sold))?$",
    re.IGNORECASE,
)
_EVENT_OPTION_RE = re.compile(r"^event\s+option\s+(?P<label>.+?)(?:\s+(?P<unavailable>unavailable|disabled))?$", re.IGNORECASE)
_REST_OPTION_RE = re.compile(r"^rest\s+option\s+(?P<option>rest|smith)(?:\s+(?P<unavailable>unavailable|disabled))?$", re.IGNORECASE)
_LEAVE_SHOP_RE = re.compile(r"^leave\s+shop$", re.IGNORECASE)
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
    shop_items: list[dict[str, Any]] = []
    event_options: list[dict[str, Any]] = []
    rest_options: list[dict[str, Any]] = []
    boxes: dict[str, Box] = {}
    field_confidence: dict[str, float] = {}
    shop_item_ids: dict[str, int] = {}
    event_option_ids: dict[str, int] = {}
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
            _record_confidence(field_confidence, "cards", token.confidence)
            consumed.add(index)
            continue
        if monster := _monster_from_text(text, len(monsters)):
            monsters.append(monster)
            boxes[f"monster:{monster['monster_id']}:{monster['slot_index']}"] = token.box
            _record_confidence(field_confidence, "monsters", token.confidence)
            consumed.add(index)
            continue
        if path := _path_from_text(text):
            paths.append(path)
            boxes[f"path:{path['node_id']}"] = token.box
            _record_confidence(field_confidence, "path_candidates", token.confidence)
            consumed.add(index)
            continue
        if potion := _potion_from_text(text):
            potions.append(potion)
            boxes[f"potion:{potion['potion_id']}:{potion['slot']}"] = token.box
            _record_confidence(field_confidence, "potions", token.confidence)
            consumed.add(index)
            continue
        if shop_item := _shop_item_from_text(text):
            shop_item["item_id"] = _slotted_id(str(shop_item["item_id"]), shop_item_ids)
            shop_items.append(shop_item)
            boxes[f"shop_item:{shop_item['item_id']}"] = token.box
            _record_confidence(field_confidence, "shop_items", token.confidence)
            consumed.add(index)
            continue
        if _LEAVE_SHOP_RE.match(text):
            leave_item = {"item_id": _slotted_id("leave_shop", shop_item_ids), "item_type": "leave", "price": 0}
            shop_items.append(leave_item)
            boxes[f"shop_item:{leave_item['item_id']}"] = token.box
            _record_confidence(field_confidence, "shop_items", token.confidence)
            consumed.add(index)
            continue
        if event_option := _event_option_from_text(text):
            event_option["option_id"] = _slotted_id(str(event_option["option_id"]), event_option_ids)
            event_options.append(event_option)
            boxes[f"event_option:{event_option['option_id']}"] = token.box
            _record_confidence(field_confidence, "event_options", token.confidence)
            consumed.add(index)
            continue
        if rest_option := _rest_option_from_text(text):
            rest_options.append(rest_option)
            boxes[f"rest_option:{rest_option['option_id']}"] = token.box
            _record_confidence(field_confidence, "rest_options", token.confidence)
            consumed.add(index)
            continue
        consumed_by_scalar = _extract_player_values(lower, player, resources, field_confidence, token.confidence)
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
    if shop_items:
        payload["shop_items"] = shop_items
    if event_options:
        payload["event_options"] = event_options
    if rest_options:
        payload["rest_options"] = rest_options
    if floor is not None:
        payload["_meta"] = {"floor": floor}

    return LiveStateExtraction(
        state_payload=payload,
        state_boxes=boxes,
        floor=floor,
        missing_fields=_missing_fields(payload),
        unknown_tokens=_unknown_tokens(tokens, consumed),
        field_confidence=field_confidence,
    )


def _extract_player_values(
    text: str,
    player: dict[str, Any],
    resources: dict[str, int],
    field_confidence: dict[str, float],
    confidence: float,
) -> bool:
    consumed = False
    if hp_match := _HP_RE.search(text):
        player["hp"] = int(hp_match.group("hp"))
        player["max_hp"] = int(hp_match.group("max_hp"))
        field_confidence["player.hp"] = confidence
        field_confidence["player.max_hp"] = confidence
        consumed = True
    for regex, key in ((_ENERGY_RE, "energy"), (_BLOCK_RE, "block"), (_TURN_RE, "turn")):
        if match := regex.search(text):
            player[key] = int(match.group(key))
            field_confidence[f"player.{key}"] = confidence
            consumed = True
    if gold_match := _GOLD_RE.search(text):
        resources["gold"] = int(gold_match.group("gold"))
        field_confidence["player.character_resource.gold"] = confidence
        consumed = True
    return consumed


def _record_confidence(field_confidence: dict[str, float], field: str, confidence: float) -> None:
    field_confidence[field] = max(confidence, field_confidence.get(field, 0.0))


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


def _shop_item_from_text(text: str) -> dict[str, Any] | None:
    match = _SHOP_ITEM_RE.match(text)
    if match is None:
        return None
    item_type = match.group("kind").casefold()
    item = {
        "item_id": _slug(match.group("label")),
        "item_type": item_type,
        "price": int(match.group("price")),
    }
    if card_id := match.group("card_id"):
        item["card_id"] = _slug(card_id)
    if removal_target := match.group("removal_target"):
        item["target_card_id"] = _slug(removal_target)
    if match.group("sold") is not None:
        item["purchasable"] = False
    return item


def _event_option_from_text(text: str) -> dict[str, Any] | None:
    match = _EVENT_OPTION_RE.match(text)
    if match is None:
        return None
    label = match.group("label")
    option = {"option_id": _slug(label), "label": label}
    if match.group("unavailable") is not None:
        option["available"] = False
    return option


def _rest_option_from_text(text: str) -> dict[str, Any] | None:
    match = _REST_OPTION_RE.match(text)
    if match is None:
        return None
    option = {"option_id": match.group("option").casefold()}
    if match.group("unavailable") is not None:
        option["available"] = False
    return option


def _missing_fields(payload: dict[str, Any]) -> list[str]:
    missing = []
    player = payload.get("player", {})
    for field in ("hp", "max_hp", "block", "energy", "turn"):
        if field not in player:
            missing.append(f"player.{field}")
    if "character_resource" not in player or "gold" not in player.get("character_resource", {}):
        missing.append("player.character_resource.gold")
    for field in ("cards", "monsters", "path_candidates", "potions", "shop_items", "event_options", "rest_options"):
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


def _slotted_id(base: str, counts: dict[str, int]) -> str:
    count = counts.get(base, 0) + 1
    counts[base] = count
    if count == 1:
        return base
    return f"{base}_{count}"


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())
