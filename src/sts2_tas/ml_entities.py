from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

Box = tuple[int, int, int, int]

ResourceValue = int | str | bool


@dataclass(frozen=True)
class PlayerState:
    hp: int
    max_hp: int
    block: int
    energy: int
    turn: int
    strength: int = 0
    dexterity: int = 0
    vulnerable: int = 0
    weak: int = 0
    frail: int = 0
    artifact: int = 0
    poison: int = 0
    regen: int = 0
    intangible: int = 0
    character_resource: dict[str, ResourceValue] | None = None

    def __post_init__(self) -> None:
        if self.hp < 0 or self.max_hp <= 0:
            raise ValueError("player hp must be non-negative and max_hp must be positive")
        if self.block < 0 or self.energy < 0 or self.turn < 0:
            raise ValueError("player block, energy, and turn must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["character_resource"] = dict(self.character_resource or {})
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlayerState:
        return cls(
            hp=int(data["hp"]),
            max_hp=int(data["max_hp"]),
            block=int(data["block"]),
            energy=int(data["energy"]),
            turn=int(data["turn"]),
            strength=int(data.get("strength", 0)),
            dexterity=int(data.get("dexterity", 0)),
            vulnerable=int(data.get("vulnerable", 0)),
            weak=int(data.get("weak", 0)),
            frail=int(data.get("frail", 0)),
            artifact=int(data.get("artifact", 0)),
            poison=int(data.get("poison", 0)),
            regen=int(data.get("regen", 0)),
            intangible=int(data.get("intangible", 0)),
            character_resource=dict(data.get("character_resource", {})),
        )


@dataclass(frozen=True)
class CardInstance:
    instance_id: str
    card_id: str
    zone: str
    upgraded: bool
    base_cost: int | None
    current_cost: int | None
    type: str
    rarity: str
    tags: list[str]
    temporary: bool = False
    generated: bool = False
    retain: bool = False
    exhaust: bool = False
    ethereal: bool = False
    innate: bool = False

    def __post_init__(self) -> None:
        if not self.instance_id or not self.card_id or not self.zone:
            raise ValueError("card instance_id, card_id, and zone are required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardInstance:
        return cls(
            instance_id=data["instance_id"],
            card_id=data["card_id"],
            zone=data["zone"],
            upgraded=bool(data["upgraded"]),
            base_cost=_optional_int(data.get("base_cost")),
            current_cost=_optional_int(data.get("current_cost")),
            type=data["type"],
            rarity=data["rarity"],
            tags=list(data["tags"]),
            temporary=bool(data.get("temporary", False)),
            generated=bool(data.get("generated", False)),
            retain=bool(data.get("retain", False)),
            exhaust=bool(data.get("exhaust", False)),
            ethereal=bool(data.get("ethereal", False)),
            innate=bool(data.get("innate", False)),
        )


@dataclass(frozen=True)
class RelicState:
    relic_id: str
    obtained_order: int
    counter: int | None = None
    cooldown: int | None = None
    activated_this_combat: bool = False
    activated_this_turn: bool = False

    def __post_init__(self) -> None:
        if not self.relic_id:
            raise ValueError("relic_id is required")
        if self.obtained_order < 0:
            raise ValueError("obtained_order must be non-negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelicState:
        return cls(
            relic_id=data["relic_id"],
            obtained_order=int(data["obtained_order"]),
            counter=_optional_int(data.get("counter")),
            cooldown=_optional_int(data.get("cooldown")),
            activated_this_combat=bool(data.get("activated_this_combat", False)),
            activated_this_turn=bool(data.get("activated_this_turn", False)),
        )


@dataclass(frozen=True)
class PotionState:
    potion_id: str
    slot: int
    requires_target: bool
    usable: bool

    def __post_init__(self) -> None:
        if not self.potion_id:
            raise ValueError("potion_id is required")
        if self.slot < 0:
            raise ValueError("potion slot must be non-negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PotionState:
        return cls(
            potion_id=data["potion_id"],
            slot=int(data["slot"]),
            requires_target=bool(data["requires_target"]),
            usable=bool(data["usable"]),
        )


@dataclass(frozen=True)
class MonsterState:
    monster_id: str
    slot_index: int
    hp: int
    max_hp: int
    block: int
    intent_type: str
    intent_damage: int
    hit_count: int
    buffs: list[str]
    debuffs: list[str]
    is_boss: bool = False
    is_minion: bool = False
    pattern_phase: str = ""

    def __post_init__(self) -> None:
        if not self.monster_id:
            raise ValueError("monster_id is required")
        if self.slot_index < 0 or self.hp < 0 or self.max_hp <= 0 or self.block < 0:
            raise ValueError("monster numeric state is invalid")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonsterState:
        return cls(
            monster_id=data["monster_id"],
            slot_index=int(data["slot_index"]),
            hp=int(data["hp"]),
            max_hp=int(data["max_hp"]),
            block=int(data["block"]),
            intent_type=data["intent_type"],
            intent_damage=int(data["intent_damage"]),
            hit_count=int(data["hit_count"]),
            buffs=list(data["buffs"]),
            debuffs=list(data["debuffs"]),
            is_boss=bool(data.get("is_boss", False)),
            is_minion=bool(data.get("is_minion", False)),
            pattern_phase=data.get("pattern_phase", ""),
        )


@dataclass(frozen=True)
class PathCandidate:
    node_id: str
    node_type: str
    depth: int
    elite_count_ahead: int
    rest_count_ahead: int
    shop_count_ahead: int
    event_count_ahead: int
    boss_distance: int
    forced_elite: bool = False

    def __post_init__(self) -> None:
        if not self.node_id or not self.node_type:
            raise ValueError("path node_id and node_type are required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathCandidate:
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            depth=int(data["depth"]),
            elite_count_ahead=int(data["elite_count_ahead"]),
            rest_count_ahead=int(data["rest_count_ahead"]),
            shop_count_ahead=int(data["shop_count_ahead"]),
            event_count_ahead=int(data["event_count_ahead"]),
            boss_distance=int(data["boss_distance"]),
            forced_elite=bool(data.get("forced_elite", False)),
        )


@dataclass(frozen=True)
class ActionCandidate:
    action_type: str
    option_id: str | None = None
    source_card_id: str | None = None
    source_potion_id: str | None = None
    target_card_id: str | None = None
    target_monster_id: str | None = None
    path_node_id: str | None = None
    shop_item_id: str | None = None
    event_option_id: str | None = None
    screen_box: Box | None = None
    legal: bool = True

    def __post_init__(self) -> None:
        if not self.action_type:
            raise ValueError("action_type is required")

    @property
    def identity(self) -> str:
        parts = [
            ("option", self.option_id),
            ("source_card", self.source_card_id),
            ("source_potion", self.source_potion_id),
            ("target_card", self.target_card_id),
            ("target_monster", self.target_monster_id),
            ("path_node", self.path_node_id),
            ("shop_item", self.shop_item_id),
            ("event_option", self.event_option_id),
        ]
        present = [(name, value) for name, value in parts if value is not None]
        if not present:
            return self.action_type
        if len(present) == 1:
            return present[0][1]
        return "|".join(f"{name}={value}" for name, value in present)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionCandidate:
        return cls(
            action_type=data["action_type"],
            option_id=data.get("option_id"),
            source_card_id=data.get("source_card_id"),
            source_potion_id=data.get("source_potion_id"),
            target_card_id=data.get("target_card_id"),
            target_monster_id=data.get("target_monster_id"),
            path_node_id=data.get("path_node_id"),
            shop_item_id=data.get("shop_item_id"),
            event_option_id=data.get("event_option_id"),
            screen_box=tuple(data["screen_box"]) if data.get("screen_box") is not None else None,  # type: ignore[arg-type]
            legal=bool(data.get("legal", True)),
        )


@dataclass(frozen=True)
class ObservationQuality:
    source_type: str
    ocr_confidence: float
    game_version: str
    branch: str
    catalog_version: str
    missing_fields: list[str] | None = None
    unknown_tokens: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["missing_fields"] = list(self.missing_fields or [])
        data["unknown_tokens"] = list(self.unknown_tokens or [])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationQuality:
        return cls(
            source_type=data["source_type"],
            ocr_confidence=float(data["ocr_confidence"]),
            game_version=data["game_version"],
            branch=data["branch"],
            catalog_version=data["catalog_version"],
            missing_fields=list(data.get("missing_fields", [])),
            unknown_tokens=list(data.get("unknown_tokens", [])),
        )


@dataclass(frozen=True)
class StepOutcome:
    victory: bool
    floor_reached: int
    hp_remaining: int
    immediate_reward: float = 0.0
    terminal: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepOutcome:
        return cls(
            victory=bool(data["victory"]),
            floor_reached=int(data["floor_reached"]),
            hp_remaining=int(data["hp_remaining"]),
            immediate_reward=float(data.get("immediate_reward", 0.0)),
            terminal=bool(data.get("terminal", False)),
        )


@dataclass(frozen=True)
class StructuredGameState:
    game_version: str
    branch: str
    catalog_version: str
    character: str
    ascension: int
    floor: int
    decision_context: str
    player: PlayerState
    cards: list[CardInstance] | None = None
    relics: list[RelicState] | None = None
    potions: list[PotionState] | None = None
    monsters: list[MonsterState] | None = None
    path_candidates: list[PathCandidate] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_version": self.game_version,
            "branch": self.branch,
            "catalog_version": self.catalog_version,
            "character": self.character,
            "ascension": self.ascension,
            "floor": self.floor,
            "decision_context": self.decision_context,
            "player": self.player.to_dict(),
            "cards": [asdict(card) for card in self.cards or []],
            "relics": [asdict(relic) for relic in self.relics or []],
            "potions": [asdict(potion) for potion in self.potions or []],
            "monsters": [asdict(monster) for monster in self.monsters or []],
            "path_candidates": [asdict(path) for path in self.path_candidates or []],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredGameState:
        return cls(
            game_version=data["game_version"],
            branch=data["branch"],
            catalog_version=data["catalog_version"],
            character=data["character"],
            ascension=int(data["ascension"]),
            floor=int(data["floor"]),
            decision_context=data["decision_context"],
            player=PlayerState.from_dict(data["player"]),
            cards=[CardInstance.from_dict(card) for card in data.get("cards", [])],
            relics=[RelicState.from_dict(relic) for relic in data.get("relics", [])],
            potions=[PotionState.from_dict(potion) for potion in data.get("potions", [])],
            monsters=[MonsterState.from_dict(monster) for monster in data.get("monsters", [])],
            path_candidates=[PathCandidate.from_dict(path) for path in data.get("path_candidates", [])],
        )


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
