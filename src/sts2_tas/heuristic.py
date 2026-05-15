from __future__ import annotations

from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


def choose_action(snapshot: TelemetrySnapshot) -> MacroAction:
    legal = snapshot.valid_actions
    if not legal:
        raise ValueError("no legal actions")
    lethal = _lethal_attack(snapshot)
    if lethal is not None:
        return lethal
    if int(snapshot.player["energy"]) <= 0:
        return _first("end_turn", legal)
    for preferred in ("play_card", "choose_reward", "choose_map_node", "shop_buy", "choose_event_option"):
        for action in legal:
            if action.action_type == preferred:
                return action
    return legal[0]


def _lethal_attack(snapshot: TelemetrySnapshot) -> MacroAction | None:
    for action in snapshot.valid_actions:
        if action.action_type != "play_card":
            continue
        hand_slot = action.args["hand_slot"]
        target_slot = action.args.get("target_slot")
        if target_slot is None or hand_slot >= len(snapshot.hand) or target_slot >= len(snapshot.enemies):
            continue
        damage = int(snapshot.hand[hand_slot].get("damage", 0))
        hp = int(snapshot.enemies[target_slot].get("hp", 0))
        if damage >= hp:
            return action
    return None


def _first(action_type: str, actions: list[MacroAction]) -> MacroAction:
    for action in actions:
        if action.action_type == action_type:
            return action
    return actions[0]
