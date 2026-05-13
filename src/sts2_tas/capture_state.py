from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .ml_entities import CardInstance, MonsterState, PathCandidate, PlayerState, PotionState, RelicState


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
    return CapturedGameState(
        player=player,
        cards=cards,
        relics=relic_states,
        potions=potions,
        monsters=monsters,
        path_candidates=path_candidates,
        missing_fields=_dedupe([*payload.get("missing_fields", []), *missing]),
        unknown_tokens=list(payload.get("unknown_tokens", [])),
    )


def _load_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state json must be an object")
    return payload


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
) -> list:
    if key not in payload:
        missing.append(key)
        return []
    return [factory(item) for item in payload[key]]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
