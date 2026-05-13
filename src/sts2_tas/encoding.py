from __future__ import annotations

from dataclasses import dataclass

from .catalog import EntityCatalog
from .ml_schema import ActionCandidate, CardInstance, GameStep, MonsterState, PathCandidate, PlayerState, PotionState, RelicState

TOKEN_TYPE_IDS = {
    "GLOBAL": 0,
    "PLAYER": 1,
    "CARD": 2,
    "RELIC": 3,
    "POTION": 4,
    "MONSTER": 5,
    "PATH": 6,
    "ACTION": 7,
    "OBSERVATION": 8,
    "DECISION_CONTEXT": 9,
}
NUMERIC_FEATURE_DIM = 16


@dataclass(frozen=True)
class EncodedGameStep:
    token_ids: list[int]
    token_types: list[int]
    numeric_features: list[list[float]]
    attention_mask: list[bool]
    action_positions: list[int]
    action_mask: list[bool]
    label_action_index: int
    outcome_value: float


def encode_game_step(step: GameStep, catalog: EntityCatalog) -> EncodedGameStep:
    token_ids: list[int] = []
    token_types: list[int] = []
    numeric_features: list[list[float]] = []

    def add(category: str, value: str, token_type: str, numeric: list[float]) -> None:
        token_ids.append(catalog.id_for(category, value))
        token_types.append(TOKEN_TYPE_IDS[token_type])
        numeric_features.append(_pad_numeric(numeric))

    state = step.state
    add("global", state.character, "GLOBAL", [state.ascension, state.floor])
    add("decision_context", state.decision_context, "DECISION_CONTEXT", [len(step.actions)])
    add("player", state.character, "PLAYER", _player_numeric(state.player))
    for card in state.cards or []:
        add("card", card.card_id, "CARD", _card_numeric(card))
    for relic in state.relics or []:
        add("relic", relic.relic_id, "RELIC", _relic_numeric(relic))
    for potion in state.potions or []:
        add("potion", potion.potion_id, "POTION", _potion_numeric(potion))
    for monster in state.monsters or []:
        add("monster", monster.monster_id, "MONSTER", _monster_numeric(monster))
    for path in state.path_candidates or []:
        add("path", path.node_type, "PATH", _path_numeric(path))
    add("observation", step.observation.source_type, "OBSERVATION", [step.observation.ocr_confidence])

    action_positions = []
    for action in step.actions:
        action_positions.append(len(token_ids))
        add("action", f"{action.action_type}:{action.identity}", "ACTION", _action_numeric(action))

    label_index = _label_index(step.actions, step.chosen_action_id)
    outcome_value = 0.0 if step.outcome is None else float(step.outcome.victory)
    return EncodedGameStep(
        token_ids=token_ids,
        token_types=token_types,
        numeric_features=numeric_features,
        attention_mask=[True] * len(token_ids),
        action_positions=action_positions,
        action_mask=[action.legal for action in step.actions],
        label_action_index=label_index,
        outcome_value=outcome_value,
    )


def _label_index(actions: list[ActionCandidate], chosen_action_id: str | None) -> int:
    if chosen_action_id is None:
        raise ValueError("training requires chosen_action_id")
    for index, action in enumerate(actions):
        if action.identity == chosen_action_id:
            if not action.legal:
                raise ValueError("chosen action must be legal")
            return index
    raise ValueError(f"chosen action is not present in action candidates: {chosen_action_id}")


def _pad_numeric(values: list[float]) -> list[float]:
    if len(values) > NUMERIC_FEATURE_DIM:
        return values[:NUMERIC_FEATURE_DIM]
    return [*values, *([0.0] * (NUMERIC_FEATURE_DIM - len(values)))]


def _bool(value: bool) -> float:
    return 1.0 if value else 0.0


def _optional(value: int | None) -> float:
    return 0.0 if value is None else float(value)


def _player_numeric(player: PlayerState) -> list[float]:
    return [
        player.hp,
        player.max_hp,
        player.block,
        player.energy,
        player.turn,
        player.strength,
        player.dexterity,
        player.vulnerable,
        player.weak,
        player.frail,
        player.artifact,
        player.poison,
        player.regen,
        player.intangible,
    ]


def _card_numeric(card: CardInstance) -> list[float]:
    return [
        _bool(card.upgraded),
        _optional(card.base_cost),
        _optional(card.current_cost),
        len(card.tags),
        _bool(card.temporary),
        _bool(card.generated),
        _bool(card.retain),
        _bool(card.exhaust),
        _bool(card.ethereal),
        _bool(card.innate),
    ]


def _relic_numeric(relic: RelicState) -> list[float]:
    return [
        relic.obtained_order,
        _optional(relic.counter),
        _optional(relic.cooldown),
        _bool(relic.activated_this_combat),
        _bool(relic.activated_this_turn),
    ]


def _potion_numeric(potion: PotionState) -> list[float]:
    return [potion.slot, _bool(potion.requires_target), _bool(potion.usable)]


def _monster_numeric(monster: MonsterState) -> list[float]:
    return [
        monster.slot_index,
        monster.hp,
        monster.max_hp,
        monster.block,
        monster.intent_damage,
        monster.hit_count,
        len(monster.buffs),
        len(monster.debuffs),
        _bool(monster.is_boss),
        _bool(monster.is_minion),
    ]


def _path_numeric(path: PathCandidate) -> list[float]:
    return [
        path.depth,
        path.elite_count_ahead,
        path.rest_count_ahead,
        path.shop_count_ahead,
        path.event_count_ahead,
        path.boss_distance,
        _bool(path.forced_elite),
    ]


def _action_numeric(action: ActionCandidate) -> list[float]:
    return [
        _bool(action.legal),
        _bool(action.option_id is not None),
        _bool(action.source_card_id is not None),
        _bool(action.source_potion_id is not None),
        _bool(action.target_card_id is not None),
        _bool(action.target_monster_id is not None),
        _bool(action.path_node_id is not None),
        _bool(action.shop_item_id is not None),
        _bool(action.event_option_id is not None),
        _bool(action.screen_box is not None),
    ]
