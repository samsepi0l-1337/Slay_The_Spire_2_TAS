from __future__ import annotations

from typing import Any

from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot

# Namu wiki STS2 scales: Ironclad 80 HP, energy 3, draw 5, A10, 3 acts.
IRONCLAD_MAX_HP = 80.0
ENERGY_CAP = 3.0
STAR_CAP = 5.0
BLOCK_CAP = 50.0
GOLD_CAP = 999.0
FLOOR_CAP = 50.0
ACT_CAP = 3.0
ENEMY_HP_CAP = 200.0
HAND_CAP = 10.0
PILE_CAP = 20.0
RELIC_CAP = 20.0
POTION_CAP = 3.0
DAMAGE_CAP = 24.0
COST_CAP = 3.0
ASCENSION_CAP = 10.0

ACTION_TYPES = (
    "play_card",
    "end_turn",
    "choose_reward",
    "choose_map_node",
    "choose_event_option",
    "shop_buy",
    "shop_remove",
)
PHASES = ("combat", "map", "event", "card_reward", "rest", "shop", "terminal")
SELF_HP_IDS = frozenset({"HEMOKINESIS", "BLOODLETTING", "OFFERING", "BRUTALITY", "COMBUST", "BREAKTHROUGH"})

FEATURE_NAMES = (
    "hp",
    "max_hp",
    "energy",
    "stars",
    "block",
    "gold",
    "floor",
    "act",
    "enemy_hp",
    "enemy_block",
    "enemy_count",
    "hand",
    "draw",
    "discard",
    "relics",
    "potions",
    "ascension",
    *tuple(f"phase_{phase}" for phase in PHASES),
    *tuple(f"act_{action_type}" for action_type in ACTION_TYPES),
    "hand_slot",
    "target_slot",
    "choice_slot",
    "damage",
    "block_gain",
    "cost",
    "energy_left",
    "is_attack",
    "is_skill",
    "is_power",
    "lethal",
    "low_hp",
    "self_hp_card",
    "intent_attack",
)

FEATURE_DIM = len(FEATURE_NAMES)
FEATURE_VERSION = 2
HIDDEN_SIZE = 32


def feature_index(name: str) -> int:
    return FEATURE_NAMES.index(name)


def feature_vector(snapshot: TelemetrySnapshot, action: MacroAction) -> list[float]:
    player = snapshot.player
    enemies = snapshot.enemies
    card = _card(snapshot, action)
    damage = int(card.get("damage", 0))
    block = int(card.get("block", 0))
    cost = int(card.get("cost", 0))
    max_hp = max(int(player.get("max_hp", IRONCLAD_MAX_HP)), 1)
    hp = int(player.get("hp", 0))
    energy = int(player.get("energy", 0))
    stars = int((player.get("resources") or {}).get("stars", 0))
    target_slot = action.args.get("target_slot")
    lethal = 0.0
    intent_attack = 0.0
    if isinstance(target_slot, int) and 0 <= target_slot < len(enemies):
        enemy = enemies[target_slot]
        enemy_hp = int(enemy.get("hp", 0))
        enemy_block = int(enemy.get("block", 0))
        if enemy_hp > 0 and max(0, damage - enemy_block) >= enemy_hp:
            lethal = 1.0
        if str(enemy.get("intent", "")).lower() == "attack":
            intent_attack = 1.0
    elif enemies:
        intent_attack = 1.0 if str(enemies[0].get("intent", "")).lower() == "attack" else 0.0
    card_type = str(card.get("type", "")).lower()
    extras = snapshot.extras
    values = [
        hp / IRONCLAD_MAX_HP,
        float(player.get("max_hp", 0)) / IRONCLAD_MAX_HP,
        energy / ENERGY_CAP,
        stars / STAR_CAP,
        float(player.get("block", 0)) / BLOCK_CAP,
        float(player.get("gold", 0)) / GOLD_CAP,
        float(snapshot.floor) / FLOOR_CAP,
        float(snapshot.act) / ACT_CAP,
        float(sum(int(enemy.get("hp", 0)) for enemy in enemies)) / ENEMY_HP_CAP,
        float(sum(int(enemy.get("block", 0)) for enemy in enemies)) / BLOCK_CAP,
        float(len(enemies)) / 5.0,
        float(len(snapshot.hand)) / HAND_CAP,
        float(len(snapshot.draw_pile)) / PILE_CAP,
        float(len(snapshot.discard_pile)) / PILE_CAP,
        float(len(snapshot.relics)) / RELIC_CAP,
        float(len(snapshot.potions)) / POTION_CAP,
        float(int(extras.get("ascension", 0))) / ASCENSION_CAP,
        *[1.0 if snapshot.phase == phase else 0.0 for phase in PHASES],
        *[1.0 if action.action_type == action_type else 0.0 for action_type in ACTION_TYPES],
        float(action.args.get("hand_slot", 0)) / HAND_CAP,
        float(action.args.get("target_slot", 0)) / 5.0,
        float(_choice_slot(action)) / 10.0,
        damage / DAMAGE_CAP,
        block / BLOCK_CAP,
        cost / COST_CAP,
        max(0.0, energy - cost) / ENERGY_CAP,
        1.0 if card_type == "attack" else 0.0,
        1.0 if card_type == "skill" else 0.0,
        1.0 if card_type == "power" else 0.0,
        lethal,
        1.0 if hp / max_hp <= 0.25 else 0.0,
        1.0 if str(card.get("id", "")).upper() in SELF_HP_IDS else 0.0,
        intent_attack,
    ]
    return values


def _card(snapshot: TelemetrySnapshot, action: MacroAction) -> dict[str, Any]:
    if action.action_type != "play_card":
        return {}
    hand_slot = action.args.get("hand_slot", 0)
    if not isinstance(hand_slot, int) or hand_slot < 0 or hand_slot >= len(snapshot.hand):
        return {}
    return snapshot.hand[hand_slot]


def _choice_slot(action: MacroAction) -> int:
    for key in ("choice_slot", "node_slot", "item_slot", "card_slot"):
        if key in action.args:
            return int(action.args[key])
    return 0
