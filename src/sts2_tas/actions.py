from __future__ import annotations

from .ml_entities import ActionCandidate, CardInstance, MonsterState, PotionState, ShopItemState, StructuredGameState


def generate_legal_actions(state: StructuredGameState, *, include_illegal: bool = False) -> list[ActionCandidate]:
    """Build state-derived action candidates for decision contexts with typed state."""
    if state.decision_context == "combat":
        return _combat_actions(state, include_illegal=include_illegal)
    if state.decision_context == "card_reward":
        return _card_reward_actions(state)
    if state.decision_context == "map":
        return [
            ActionCandidate(action_type="choose_path", path_node_id=path.node_id)
            for path in state.path_candidates or []
        ]
    if state.decision_context == "shop":
        return _shop_actions(state.shop_items or [])
    if state.decision_context == "event":
        return [
            ActionCandidate(action_type="choose_event_option", event_option_id=option.option_id)
            for option in state.event_options or []
            if option.available
        ]
    if state.decision_context == "rest":
        return [
            ActionCandidate(action_type=option.option_id)
            for option in state.rest_options or []
            if option.available and option.option_id in {"rest", "smith"}
        ]
    return []


def _combat_actions(state: StructuredGameState, *, include_illegal: bool) -> list[ActionCandidate]:
    monsters = _living_monsters(state.monsters or [])
    actions: list[ActionCandidate] = []
    for card in _hand_cards(state.cards or []):
        legal = _card_is_playable(card, energy=state.player.energy)
        if legal or include_illegal:
            actions.extend(_card_actions(card, monsters, legal=legal))
    for potion in state.potions or []:
        if potion.usable:
            actions.extend(_potion_actions(potion, monsters))
    actions.append(ActionCandidate(action_type="end_turn"))
    return actions


def _card_reward_actions(state: StructuredGameState) -> list[ActionCandidate]:
    actions = [
        ActionCandidate(action_type="pick_card", target_card_id=card.instance_id)
        for card in state.cards or []
        if card.zone == "reward"
    ]
    actions.append(ActionCandidate(action_type="skip_reward", option_id="skip"))
    return actions


def _shop_actions(items: list[ShopItemState]) -> list[ActionCandidate]:
    actions: list[ActionCandidate] = []
    for item in items:
        if item.item_type == "leave":
            continue
        if not item.purchasable:
            continue
        if item.item_type == "remove":
            if item.removal_target is not None:
                actions.append(
                    ActionCandidate(
                        action_type="remove_card",
                        target_card_id=item.removal_target,
                        shop_item_id=item.item_id,
                    )
                )
            continue
        actions.append(ActionCandidate(action_type="buy", shop_item_id=item.item_id))
    actions.append(ActionCandidate(action_type="leave_shop"))
    return actions


def _hand_cards(cards: list[CardInstance]) -> list[CardInstance]:
    return [card for card in cards if card.zone == "hand"]


def _living_monsters(monsters: list[MonsterState]) -> list[MonsterState]:
    return [monster for monster in monsters if monster.hp > 0]


def _card_is_playable(card: CardInstance, *, energy: int) -> bool:
    cost = card.current_cost if card.current_cost is not None else card.base_cost
    return cost is not None and cost <= energy


def _card_actions(card: CardInstance, monsters: list[MonsterState], *, legal: bool) -> list[ActionCandidate]:
    if _card_requires_monster_target(card):
        return [
            ActionCandidate(
                action_type="play_card",
                source_card_id=card.instance_id,
                target_monster_id=_monster_identity(monster),
                legal=legal,
            )
            for monster in monsters
        ]
    return [ActionCandidate(action_type="play_card", source_card_id=card.instance_id, legal=legal)]


def _card_requires_monster_target(card: CardInstance) -> bool:
    return card.type == "attack" or "attack" in card.tags or "target" in card.tags


def _potion_actions(potion: PotionState, monsters: list[MonsterState]) -> list[ActionCandidate]:
    source = f"{potion.potion_id}:{potion.slot}"
    if potion.requires_target:
        return [
            ActionCandidate(
                action_type="use_potion",
                source_potion_id=source,
                target_monster_id=_monster_identity(monster),
            )
            for monster in monsters
        ]
    return [ActionCandidate(action_type="use_potion", source_potion_id=source)]


def _monster_identity(monster: MonsterState) -> str:
    return f"{monster.monster_id}:{monster.slot_index}"
