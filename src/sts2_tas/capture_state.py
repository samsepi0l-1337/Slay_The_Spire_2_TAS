from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .ml_entities import (
    CardInstance,
    EventOptionState,
    MonsterState,
    PathCandidate,
    PlayerState,
    PotionState,
    RelicState,
    RestOptionState,
    ShopItemState,
)


@dataclass(frozen=True)
class CapturedGameState:
    player: PlayerState
    cards: list[CardInstance]
    relics: list[RelicState]
    potions: list[PotionState]
    monsters: list[MonsterState]
    path_candidates: list[PathCandidate]
    missing_fields: list[str]
    unknown_tokens: list[str]
    shop_items: list[ShopItemState] | None = None
    event_options: list[EventOptionState] | None = None
    rest_options: list[RestOptionState] | None = None


def overlay_captured_game_state(
    captured: CapturedGameState,
    payload: dict[str, Any] | None,
    *,
    missing_fields: list[str] | None = None,
    unknown_tokens: list[str] | None = None,
) -> CapturedGameState:
    if not payload and not missing_fields and not unknown_tokens:
        return captured
    payload = payload or {}
    player = _overlay_player(captured.player, payload.get("player", {}))
    cards = _overlay_entities(captured.cards, payload, "cards", CardInstance.from_dict)
    relics = _overlay_entities(captured.relics, payload, "relics", RelicState.from_dict)
    potions = _overlay_entities(captured.potions, payload, "potions", PotionState.from_dict)
    monsters = _overlay_entities(captured.monsters, payload, "monsters", MonsterState.from_dict)
    paths = _overlay_entities(captured.path_candidates, payload, "path_candidates", PathCandidate.from_dict)
    shop_items = _overlay_entities(captured.shop_items or [], payload, "shop_items", ShopItemState.from_dict)
    event_options = _overlay_entities(captured.event_options or [], payload, "event_options", EventOptionState.from_dict)
    rest_options = _overlay_entities(captured.rest_options or [], payload, "rest_options", RestOptionState.from_dict)
    return CapturedGameState(
        player=player,
        cards=cards,
        relics=relics,
        potions=potions,
        monsters=monsters,
        path_candidates=paths,
        missing_fields=_dedupe(
            [
                *_unresolved_missing(captured.missing_fields, payload),
                *(missing_fields or []),
            ]
        ),
        unknown_tokens=_dedupe([*captured.unknown_tokens, *(unknown_tokens or [])]),
        shop_items=shop_items,
        event_options=event_options,
        rest_options=rest_options,
    )


def load_captured_game_state(
    *,
    state_json: Path | None,
    deck: list[str],
    relics: list[str],
    hp: int,
    gold: int,
    max_hp: int | None,
    block: int | None,
    energy: int | None,
    turn: int | None,
    strength: int | None,
    dexterity: int | None,
    vulnerable: int | None,
    weak: int | None,
    frail: int | None,
    artifact: int | None,
    poison: int | None,
    regen: int | None,
    intangible: int | None,
) -> CapturedGameState:
    payload = _load_payload(state_json)
    missing: list[str] = []
    player = _player_from_inputs(
        payload.get("player", {}),
        missing=missing,
        hp=hp,
        gold=gold,
        max_hp=max_hp,
        block=block,
        energy=energy,
        turn=turn,
        strength=strength,
        dexterity=dexterity,
        vulnerable=vulnerable,
        weak=weak,
        frail=frail,
        artifact=artifact,
        poison=poison,
        regen=regen,
        intangible=intangible,
    )
    cards = _cards_from_inputs(payload, deck, missing)
    relic_states = _relics_from_inputs(payload, relics, missing)
    potions = _entities_from_payload(payload, "potions", PotionState.from_dict, missing)
    monsters = _entities_from_payload(payload, "monsters", MonsterState.from_dict, missing)
    path_candidates = _entities_from_payload(payload, "path_candidates", PathCandidate.from_dict, missing)
    shop_items = _entities_from_payload(payload, "shop_items", ShopItemState.from_dict, missing, optional=True)
    event_options = _entities_from_payload(payload, "event_options", EventOptionState.from_dict, missing, optional=True)
    rest_options = _entities_from_payload(payload, "rest_options", RestOptionState.from_dict, missing, optional=True)
    return CapturedGameState(
        player=player,
        cards=cards,
        relics=relic_states,
        potions=potions,
        monsters=monsters,
        path_candidates=path_candidates,
        missing_fields=_dedupe([*payload.get("missing_fields", []), *missing]),
        unknown_tokens=list(payload.get("unknown_tokens", [])),
        shop_items=shop_items,
        event_options=event_options,
        rest_options=rest_options,
    )


def _load_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state json must be an object")
    return payload


def _overlay_player(player: PlayerState, payload: dict[str, Any]) -> PlayerState:
    if not payload:
        return player
    data = player.to_dict()
    resources = dict(data.get("character_resource", {}))
    resources.update(dict(payload.get("character_resource", {})))
    for key, value in payload.items():
        if key != "character_resource":
            data[key] = value
    data["character_resource"] = resources
    return PlayerState.from_dict(data)


def _overlay_entities(current: list, payload: dict[str, Any], key: str, factory) -> list:
    if key not in payload:
        return current
    return [factory(item) for item in payload[key]]


def _unresolved_missing(missing: list[str], payload: dict[str, Any]) -> list[str]:
    observed = set()
    if "player" in payload:
        for key in payload["player"]:
            if key == "character_resource":
                for resource in payload["player"]["character_resource"]:
                    observed.add(f"player.character_resource.{resource}")
            else:
                observed.add(f"player.{key}")
    for key in (
        "cards",
        "relics",
        "potions",
        "monsters",
        "path_candidates",
        "shop_items",
        "event_options",
        "rest_options",
    ):
        if key in payload:
            observed.add(key)
    return [field for field in missing if not _missing_field_observed(field, observed)]


def _missing_field_observed(field: str, observed: set[str]) -> bool:
    if field in observed:
        return True
    entity_root = field.split(".", 1)[0]
    entity_roots = {
        "cards",
        "relics",
        "potions",
        "monsters",
        "path_candidates",
        "shop_items",
        "event_options",
        "rest_options",
    }
    return entity_root in entity_roots and entity_root in observed


def _player_from_inputs(
    data: dict[str, Any],
    *,
    missing: list[str],
    hp: int,
    gold: int,
    max_hp: int | None,
    block: int | None,
    energy: int | None,
    turn: int | None,
    strength: int | None,
    dexterity: int | None,
    vulnerable: int | None,
    weak: int | None,
    frail: int | None,
    artifact: int | None,
    poison: int | None,
    regen: int | None,
    intangible: int | None,
) -> PlayerState:
    resources = dict(data.get("character_resource", {}))
    resources.setdefault("gold", gold)
    return PlayerState(
        hp=_player_value(data, "hp", hp, missing),
        max_hp=_player_value(data, "max_hp", max_hp, missing, fallback=max(hp, 1)),
        block=_player_value(data, "block", block, missing, fallback=0),
        energy=_player_value(data, "energy", energy, missing, fallback=0),
        turn=_player_value(data, "turn", turn, missing, fallback=0),
        strength=_player_value(data, "strength", strength, missing, fallback=0),
        dexterity=_player_value(data, "dexterity", dexterity, missing, fallback=0),
        vulnerable=_player_value(data, "vulnerable", vulnerable, missing, fallback=0),
        weak=_player_value(data, "weak", weak, missing, fallback=0),
        frail=_player_value(data, "frail", frail, missing, fallback=0),
        artifact=_player_value(data, "artifact", artifact, missing, fallback=0),
        poison=_player_value(data, "poison", poison, missing, fallback=0),
        regen=_player_value(data, "regen", regen, missing, fallback=0),
        intangible=_player_value(data, "intangible", intangible, missing, fallback=0),
        character_resource=resources,
    )


def _player_value(
    data: dict[str, Any],
    name: str,
    cli_value: int | None,
    missing: list[str],
    *,
    fallback: int | None = None,
) -> int:
    if name in data:
        return int(data[name])
    if cli_value is not None:
        return cli_value
    if fallback is None:
        raise ValueError(f"player.{name} is required")
    missing.append(f"player.{name}")
    return fallback


def _cards_from_inputs(payload: dict[str, Any], deck: list[str], missing: list[str]) -> list[CardInstance]:
    if "cards" in payload:
        return [CardInstance.from_dict(card) for card in payload["cards"]]
    if not deck:
        missing.append("cards")
        return []
    missing.append("cards.metadata")
    return [
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
        for index, card_id in enumerate(deck)
    ]


def _relics_from_inputs(payload: dict[str, Any], relics: list[str], missing: list[str]) -> list[RelicState]:
    if "relics" in payload:
        return [RelicState.from_dict(relic) for relic in payload["relics"]]
    if not relics:
        missing.append("relics")
        return []
    missing.append("relics.counters")
    return [RelicState(relic_id=relic_id, obtained_order=index) for index, relic_id in enumerate(relics)]


def _entities_from_payload(
    payload: dict[str, Any],
    key: str,
    factory,
    missing: list[str],
    *,
    optional: bool = False,
) -> list:
    if key not in payload:
        if not optional:
            missing.append(key)
        return []
    return [factory(item) for item in payload[key]]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
