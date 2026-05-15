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
class ShopItemState:
    item_id: str
    item_type: str
    price: int
    purchasable: bool = True
    card_id: str | None = None
    target_card_id: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id or not self.item_type:
            raise ValueError("shop item_id and item_type are required")
        if self.price < 0:
            raise ValueError("shop item price must be non-negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShopItemState:
        return cls(
            item_id=data["item_id"],
            item_type=data["item_type"],
            price=int(data["price"]),
            purchasable=bool(data.get("purchasable", True)),
            card_id=data.get("card_id"),
            target_card_id=data.get("target_card_id"),
        )

    @property
    def removal_target(self) -> str | None:
        return self.target_card_id or self.card_id


@dataclass(frozen=True)
class EventOptionState:
    option_id: str
    label: str
    available: bool = True

    def __post_init__(self) -> None:
        if not self.option_id:
            raise ValueError("event option_id is required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventOptionState:
        return cls(
            option_id=data["option_id"],
            label=data.get("label", ""),
            available=bool(data.get("available", True)),
        )


@dataclass(frozen=True)
class RestOptionState:
    option_id: str
    available: bool = True

    def __post_init__(self) -> None:
        if not self.option_id:
            raise ValueError("rest option_id is required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RestOptionState:
        return cls(
            option_id=data["option_id"],
            available=bool(data.get("available", True)),
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
    target_screen_box: Box | None = None
    legal: bool = True

    def __post_init__(self) -> None:
        if not self.action_type:
            raise ValueError("action_type is required")

    @property
    def identity_fields(self) -> tuple[tuple[str, str], ...]:
        if self.action_type == "remove_card" and self.target_card_id is not None:
            return (("target_card", self.target_card_id),)
        if self.option_id is not None:
            return (("option", self.option_id),)
        fields = (
            ("source_card", self.source_card_id),
            ("source_potion", self.source_potion_id),
            ("target_card", self.target_card_id),
            ("target_monster", self.target_monster_id),
            ("path_node", self.path_node_id),
            ("shop_item", self.shop_item_id),
            ("event_option", self.event_option_id),
        )
        return tuple((name, value) for name, value in fields if value is not None)

    @property
    def identity(self) -> str:
        if not self.identity_fields:
            return self.action_type
        fields = "|".join(f"{name}={value}" for name, value in self.identity_fields)
        return f"{self.action_type}|{fields}"

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
            target_screen_box=tuple(data["target_screen_box"]) if data.get("target_screen_box") is not None else None,  # type: ignore[arg-type]
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
    field_confidence: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["missing_fields"] = list(self.missing_fields or [])
        data["unknown_tokens"] = list(self.unknown_tokens or [])
        data["field_confidence"] = dict(self.field_confidence or {})
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
            field_confidence={key: float(value) for key, value in data.get("field_confidence", {}).items()},
        )


@dataclass(frozen=True)
class StepOutcome:
    victory: bool
    floor_reached: int
    hp_remaining: int
    immediate_reward: float = 0.0
    terminal: bool = False
    value_target: float | None = None
    discounted_return: float | None = None

    def __post_init__(self) -> None:
        _validate_unit_interval(self.value_target, "value_target")
        _validate_unit_interval(self.discounted_return, "discounted_return")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepOutcome:
        return cls(
            victory=bool(data["victory"]),
            floor_reached=int(data["floor_reached"]),
            hp_remaining=int(data["hp_remaining"]),
            immediate_reward=float(data.get("immediate_reward", 0.0)),
            terminal=bool(data.get("terminal", False)),
            value_target=_optional_float(data.get("value_target")),
            discounted_return=_optional_float(data.get("discounted_return")),
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
    shop_items: list[ShopItemState] | None = None
    event_options: list[EventOptionState] | None = None
    rest_options: list[RestOptionState] | None = None

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
            "shop_items": [asdict(item) for item in self.shop_items or []],
            "event_options": [asdict(option) for option in self.event_options or []],
            "rest_options": [asdict(option) for option in self.rest_options or []],
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
            shop_items=[ShopItemState.from_dict(item) for item in data.get("shop_items", [])],
            event_options=[EventOptionState.from_dict(option) for option in data.get("event_options", [])],
            rest_options=[RestOptionState.from_dict(option) for option in data.get("rest_options", [])],
        )


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _validate_unit_interval(value: float | None, field_name: str) -> None:
    if value is not None and not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def action_choice_aliases(action: ActionCandidate) -> set[str]:
    aliases = {action.identity}
    fields = action.identity_fields
    if not fields:
        aliases.add(action.action_type)
        return aliases
    field_identity = "|".join(f"{name}={value}" for name, value in fields)
    action_verb = "skip" if action.action_type in {"skip_reward", "end_turn"} else "pick"
    aliases.add(field_identity)
    aliases.add(f"{action.action_type}:{field_identity}")
    aliases.add(f"{action_verb}:{field_identity}")
    if len(fields) == 1:
        name, value = fields[0]
        aliases.update(
            {
                value,
                f"{action.action_type}:{value}",
                f"{action_verb}:{value}",
                f"{name}={value}",
                f"{action.action_type}:{name}={value}",
                f"{action_verb}:{name}={value}",
            }
        )
    if action.action_type == "skip_reward" and action.option_id == "skip":
        aliases.add("skip")
    return aliases


def resolve_action_identity(actions: list[ActionCandidate], choice: str, *, legal_only: bool = True) -> str:
    matches = [action for action in actions if choice in action_choice_aliases(action)]
    if not matches:
        raise ValueError(f"action_id is not present in game step actions: {choice}")
    legal_matches = [action for action in matches if action.legal]
    if legal_only and not legal_matches:
        raise ValueError(f"action_id is not legal: {choice}")
    candidates = legal_matches if legal_only else matches
    identities = {action.identity for action in candidates}
    if len(identities) > 1:
        raise ValueError(f"ambiguous action choice: {choice}")
    return candidates[0].identity
