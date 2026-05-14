from sts2_tas.actions import generate_legal_actions
from sts2_tas.schema import (
    CardInstance,
    MonsterState,
    PathCandidate,
    PlayerState,
    PotionState,
    StructuredGameState,
)


def _state(
    *,
    decision_context: str,
    cards: list[CardInstance] | None = None,
    monsters: list[MonsterState] | None = None,
    path_candidates: list[PathCandidate] | None = None,
    potions: list[PotionState] | None = None,
) -> StructuredGameState:
    return StructuredGameState(
        game_version="0.105.1",
        branch="beta",
        catalog_version="test-catalog",
        character="ironclad",
        ascension=0,
        floor=1,
        decision_context=decision_context,
        player=PlayerState(hp=70, max_hp=80, block=0, energy=2, turn=1),
        cards=cards or [],
        potions=potions or [],
        monsters=monsters or [],
        path_candidates=path_candidates or [],
    )


def test_generate_combat_actions_links_cards_potions_targets_and_end_turn() -> None:
    state = _state(
        decision_context="combat",
        cards=[
            CardInstance("hand-strike", "strike", "hand", False, 1, 1, "attack", "basic", ["attack"]),
            CardInstance("hand-defend", "defend", "hand", False, 1, 1, "skill", "basic", ["skill"]),
            CardInstance("hand-expensive", "bash", "hand", False, 3, 3, "attack", "basic", ["attack"]),
        ],
        potions=[PotionState("fire_potion", 0, True, True)],
        monsters=[
            MonsterState("jaw_worm", 0, 10, 40, 0, "attack", 7, 1, [], []),
            MonsterState("cultist", 1, 12, 48, 0, "buff", 0, 0, [], []),
        ],
    )

    actions = generate_legal_actions(state)

    assert [action.identity for action in actions] == [
        "play_card|source_card=hand-strike|target_monster=jaw_worm:0",
        "play_card|source_card=hand-strike|target_monster=cultist:1",
        "play_card|source_card=hand-defend",
        "use_potion|source_potion=fire_potion:0|target_monster=jaw_worm:0",
        "use_potion|source_potion=fire_potion:0|target_monster=cultist:1",
        "end_turn",
    ]
    assert all(action.legal for action in actions)


def test_generate_combat_actions_can_keep_illegal_mask_candidates() -> None:
    state = _state(
        decision_context="combat",
        cards=[CardInstance("hand-bash", "bash", "hand", False, 3, 3, "attack", "basic", ["attack"])],
        monsters=[MonsterState("jaw_worm", 0, 10, 40, 0, "attack", 7, 1, [], [])],
    )

    actions = generate_legal_actions(state, include_illegal=True)

    assert [action.identity for action in actions] == [
        "play_card|source_card=hand-bash|target_monster=jaw_worm:0",
        "end_turn",
    ]
    assert [action.legal for action in actions] == [False, True]


def test_generate_reward_and_map_actions_from_structured_state() -> None:
    reward_state = _state(
        decision_context="card_reward",
        cards=[
            CardInstance("reward-0-strike", "strike", "reward", False, None, None, "attack", "basic", ["attack"]),
            CardInstance("deck-defend", "defend", "deck", False, None, None, "skill", "basic", ["skill"]),
        ],
    )
    map_state = _state(
        decision_context="map",
        path_candidates=[
            PathCandidate("node-a", "monster", 1, 0, 1, 0, 2, 5),
            PathCandidate("node-b", "elite", 1, 1, 0, 0, 1, 5, True),
        ],
    )

    reward_actions = generate_legal_actions(reward_state)
    map_actions = generate_legal_actions(map_state)

    assert [action.identity for action in reward_actions] == [
        "pick_card|target_card=reward-0-strike",
        "skip_reward|option=skip",
    ]
    assert [action.identity for action in map_actions] == [
        "choose_path|path_node=node-a",
        "choose_path|path_node=node-b",
    ]


def test_generate_actions_handles_unsupported_context_and_untargeted_potions() -> None:
    unsupported = _state(decision_context="event")
    combat = _state(
        decision_context="combat",
        potions=[PotionState("energy_potion", 0, False, True)],
    )

    assert generate_legal_actions(unsupported) == []
    assert [action.identity for action in generate_legal_actions(combat)] == [
        "use_potion|source_potion=energy_potion:0",
        "end_turn",
    ]


def test_generate_actions_drops_target_required_actions_without_targets() -> None:
    combat = _state(
        decision_context="combat",
        cards=[CardInstance("hand-strike", "strike", "hand", False, 1, 1, "attack", "basic", ["attack"])],
        potions=[PotionState("fire_potion", 0, True, True)],
    )

    assert [action.identity for action in generate_legal_actions(combat)] == ["end_turn"]
    assert [action.identity for action in generate_legal_actions(combat, include_illegal=True)] == ["end_turn"]
