from pathlib import Path

from sts2_tas.capture_state import load_captured_game_state
from sts2_tas.schema import ParsedScreen, RecognizedOption
from sts2_tas.step_factory import _reward_option_binding, game_step_from_parsed_screen


def _captured(*, gold: int = 0):
    return load_captured_game_state(
        state_json=None,
        deck=[],
        relics=[],
        hp=70,
        gold=gold,
        max_hp=80,
        block=0,
        energy=3,
        turn=1,
        strength=None,
        dexterity=None,
        vulnerable=None,
        weak=None,
        frail=None,
        artifact=None,
        poison=None,
        regen=None,
        intangible=None,
    )


def test_step_factory_uses_live_combat_state_for_legal_actions_and_screen_boxes() -> None:
    parsed = ParsedScreen(
        "combat",
        [],
        Path("combat.png"),
        (1920, 1080),
        state_payload={
            "player": {"hp": 70, "max_hp": 80, "block": 0, "energy": 1, "turn": 1},
            "cards": [
                {
                    "instance_id": "hand-0-strike",
                    "card_id": "strike",
                    "zone": "hand",
                    "upgraded": False,
                    "base_cost": 1,
                    "current_cost": 1,
                    "type": "attack",
                    "rarity": "basic",
                    "tags": ["attack"],
                }
            ],
            "potions": [{"potion_id": "energy_potion", "slot": 0, "requires_target": False, "usable": True}],
            "monsters": [
                {
                    "monster_id": "jaw_worm",
                    "slot_index": 0,
                    "hp": 30,
                    "max_hp": 44,
                    "block": 0,
                    "intent_type": "attack",
                    "intent_damage": 7,
                    "hit_count": 1,
                    "buffs": [],
                    "debuffs": [],
                }
            ],
        },
        state_boxes={
            "card:hand-0-strike": (100, 800, 220, 980),
            "potion:energy_potion:0": (430, 920, 500, 990),
            "monster:jaw_worm:0": (1200, 310, 1520, 620),
        },
        field_confidence={
            "player.hp": 0.99,
            "player.max_hp": 0.99,
            "player.block": 0.99,
            "player.energy": 0.99,
            "player.turn": 0.99,
            "cards": 0.99,
            "monsters": 0.99,
        },
    )

    step = game_step_from_parsed_screen(
        parsed=parsed,
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )

    assert [action.identity for action in step.actions] == [
        "play_card|source_card=hand-0-strike|target_monster=jaw_worm:0",
        "use_potion|source_potion=energy_potion:0",
        "end_turn",
    ]
    assert step.actions[0].screen_box == (100, 800, 220, 980)
    assert step.actions[0].target_screen_box == (1200, 310, 1520, 620)
    assert step.actions[1].screen_box == (430, 920, 500, 990)


def test_step_factory_uses_live_map_state_for_path_actions_and_floor_override() -> None:
    parsed = ParsedScreen(
        "map",
        [],
        Path("map.png"),
        (1920, 1080),
        state_payload={
            "_meta": {"floor": 4},
            "path_candidates": [
                {
                    "node_id": "node-a",
                    "node_type": "elite",
                    "depth": 1,
                    "elite_count_ahead": 1,
                    "rest_count_ahead": 0,
                    "shop_count_ahead": 0,
                    "event_count_ahead": 1,
                    "boss_distance": 5,
                    "forced_elite": True,
                }
            ],
        },
        state_boxes={"path:node-a": (700, 230, 820, 350)},
        field_confidence={"path_candidates": 0.99},
    )

    step = game_step_from_parsed_screen(
        parsed=parsed,
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )

    assert step.state.floor == 4
    assert step.actions[0].identity == "choose_path|path_node=node-a"
    assert step.actions[0].screen_box == (700, 230, 820, 350)


def test_step_factory_keeps_reward_option_aliases_on_generated_card_reward_actions() -> None:
    parsed = ParsedScreen(
        "card_reward",
        [
            RecognizedOption("strike", "Strike", "card", (250, 260, 430, 330), 0.99, "Strike", ["attack"]),
            RecognizedOption("defend", "Defend", "card", (760, 260, 940, 330), 0.99, "Defend", ["skill"]),
            RecognizedOption("bash", "Bash", "card", (1270, 260, 1450, 330), 0.99, "Bash", ["attack"]),
            RecognizedOption("skip", "Skip", "skip", (880, 930, 1040, 990), 0.99, "Skip", []),
        ],
        Path("reward.png"),
        (1920, 1080),
    )

    step = game_step_from_parsed_screen(
        parsed=parsed,
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )

    assert [action.identity for action in step.actions] == [
        "pick_card|option=strike",
        "pick_card|option=defend",
        "pick_card|option=bash",
        "skip_reward|option=skip",
    ]
    assert step.actions[0].target_card_id == "reward-0-strike"
    assert _reward_option_binding("external-reward", []) == (None, None)


def test_step_factory_binds_live_shop_event_and_rest_action_boxes() -> None:
    shop = game_step_from_parsed_screen(
        parsed=ParsedScreen(
            "shop",
            [],
            Path("shop.png"),
            (1920, 1080),
            state_payload={
                "shop_items": [
                    {"item_id": "strike_plus", "item_type": "card", "price": 75, "card_id": "strike"},
                    {"item_id": "remove_slot", "item_type": "remove", "price": 100, "card_id": "defend"},
                    {"item_id": "leave_shop", "item_type": "leave", "price": 0},
                ],
            },
            state_boxes={
                "shop_item:strike_plus": (100, 100, 260, 220),
                "shop_item:remove_slot": (320, 100, 480, 220),
                "shop_item:leave_shop": (1700, 930, 1880, 1010),
            },
            field_confidence={"shop_items": 0.99},
        ),
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(gold=200),
        source_type="fixture",
    )
    event = game_step_from_parsed_screen(
        parsed=ParsedScreen(
            "event",
            [],
            Path("event.png"),
            (1920, 1080),
            state_payload={"event_options": [{"option_id": "take_gold", "label": "Take gold"}]},
            state_boxes={"event_option:take_gold": (500, 720, 1500, 780)},
            field_confidence={"event_options": 0.99},
        ),
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )
    rest = game_step_from_parsed_screen(
        parsed=ParsedScreen(
            "rest",
            [],
            Path("rest.png"),
            (1920, 1080),
            state_payload={"rest_options": [{"option_id": "rest"}, {"option_id": "smith"}]},
            state_boxes={"rest_option:rest": (690, 430, 830, 570), "rest_option:smith": (1000, 430, 1140, 570)},
            field_confidence={"rest_options": 0.99},
        ),
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )

    assert [(action.identity, action.screen_box) for action in shop.actions] == [
        ("buy|shop_item=strike_plus", (100, 100, 260, 220)),
        ("remove_card|target_card=defend", (320, 100, 480, 220)),
        ("leave_shop", (1700, 930, 1880, 1010)),
    ]
    assert [(action.identity, action.screen_box) for action in event.actions] == [
        ("choose_event_option|event_option=take_gold", (500, 720, 1500, 780)),
    ]
    assert [(action.identity, action.screen_box) for action in rest.actions] == [
        ("rest", (690, 430, 830, 570)),
        ("smith", (1000, 430, 1140, 570)),
    ]


def test_step_factory_fail_closed_excludes_leave_shop_action_without_observed_leave_shop_box() -> None:
    step = game_step_from_parsed_screen(
        parsed=ParsedScreen(
            "shop",
            [],
            Path("shop.png"),
            (1920, 1080),
            state_payload={
                "shop_items": [
                    {"item_id": "strike_plus", "item_type": "card", "price": 75, "card_id": "strike"},
                    {"item_id": "strike_plus_2", "item_type": "card", "price": 75, "card_id": "strike"},
                ],
            },
            state_boxes={
                "shop_item:strike_plus": (100, 100, 260, 220),
                "shop_item:strike_plus_2": (320, 100, 480, 220),
            },
            field_confidence={"shop_items": 0.99},
        ),
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(gold=200),
        source_type="fixture",
    )

    assert [(action.identity, action.screen_box) for action in step.actions] == [
        ("buy|shop_item=strike_plus", (100, 100, 260, 220)),
        ("buy|shop_item=strike_plus_2", (320, 100, 480, 220)),
    ]


def test_step_factory_binds_duplicate_event_option_ids_to_separate_boxes() -> None:
    step = game_step_from_parsed_screen(
        parsed=ParsedScreen(
            "event",
            [],
            Path("event.png"),
            (1920, 1080),
            state_payload={
                "event_options": [
                    {"option_id": "take_gold", "label": "Take gold"},
                    {"option_id": "take_gold_2", "label": "Take gold"},
                ],
            },
            state_boxes={
                "event_option:take_gold": (500, 720, 1500, 780),
                "event_option:take_gold_2": (500, 820, 1500, 880),
            },
            field_confidence={"event_options": 0.99},
        ),
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured(),
        source_type="fixture",
    )

    assert [(action.identity, action.screen_box) for action in step.actions] == [
        ("choose_event_option|event_option=take_gold", (500, 720, 1500, 780)),
        ("choose_event_option|event_option=take_gold_2", (500, 820, 1500, 880)),
    ]
