from pathlib import Path

import pytest

from sts2_tas.schema import (
    ActionCandidate,
    CardInstance,
    EventOptionState,
    GameStep,
    MonsterState,
    ObservationQuality,
    PathCandidate,
    PlayerState,
    PotionState,
    RelicState,
    RestOptionState,
    ShopItemState,
    StepOutcome,
    StructuredGameState,
)
from sts2_tas.ml_entities import action_choice_aliases, resolve_action_identity
from sts2_tas.capture_state import CapturedGameState
from sts2_tas.step_factory import (
    PerceptionQualityError,
    _action_type,
    _card_type,
    _state_with_reward_cards,
    game_step_from_parsed_screen,
)
from sts2_tas.schema import ParsedScreen


def _game_step() -> GameStep:
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=1,
            floor=7,
            decision_context="card_reward",
            player=PlayerState(
                hp=55,
                max_hp=80,
                block=3,
                energy=2,
                turn=4,
                strength=1,
                dexterity=2,
                vulnerable=0,
                weak=1,
                frail=0,
                artifact=0,
                poison=0,
                regen=0,
                intangible=0,
                character_resource={"rage": 2, "stance": "neutral", "charged": True},
            ),
            cards=[
                CardInstance(
                    instance_id="deck-anger",
                    card_id="anger",
                    zone="deck",
                    upgraded=False,
                    base_cost=0,
                    current_cost=0,
                    type="attack",
                    rarity="common",
                    tags=["attack"],
                )
            ],
            relics=[
                RelicState(
                    relic_id="burning_blood",
                    obtained_order=0,
                    counter=3,
                    cooldown=0,
                    activated_this_combat=True,
                    activated_this_turn=False,
                )
            ],
            potions=[PotionState(potion_id="fire_potion", slot=0, requires_target=True, usable=True)],
            monsters=[
                MonsterState(
                    monster_id="jaw_worm",
                    slot_index=0,
                    hp=30,
                    max_hp=44,
                    block=6,
                    intent_type="attack",
                    intent_damage=11,
                    hit_count=1,
                    buffs=["strength:2"],
                    debuffs=["weak:1"],
                    is_boss=False,
                    is_minion=False,
                    pattern_phase="opening",
                )
            ],
            path_candidates=[
                PathCandidate(
                    node_id="n7",
                    node_type="elite",
                    depth=1,
                    elite_count_ahead=2,
                    rest_count_ahead=1,
                    shop_count_ahead=0,
                    event_count_ahead=1,
                    boss_distance=8,
                    forced_elite=True,
                )
            ],
            shop_items=[ShopItemState("strike_plus", "card", 75, True, "strike")],
            event_options=[EventOptionState("take_gold", "Take gold")],
            rest_options=[RestOptionState("rest")],
        ),
        actions=[
            ActionCandidate(action_type="pick_card", option_id="anger", legal=True),
            ActionCandidate(action_type="skip_reward", option_id="skip", legal=True),
            ActionCandidate(action_type="play_card", source_card_id="deck-anger", target_monster_id="jaw_worm", legal=False),
        ],
        chosen_action_id="anger",
        outcome=StepOutcome(victory=True, floor_reached=8, hp_remaining=58, immediate_reward=0.25, terminal=False),
        observation=ObservationQuality(
            source_type="ocr",
            ocr_confidence=0.92,
            missing_fields=["draw_pile_order"],
            unknown_tokens=["new_card"],
            field_confidence={"player.hp": 0.91, "cards": 0.88},
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
        ),
        screenshot_path=Path("fixture.png"),
    )


def _captured_state() -> CapturedGameState:
    return CapturedGameState(
        player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        cards=[],
        relics=[],
        potions=[],
        monsters=[],
        path_candidates=[],
        missing_fields=[],
        unknown_tokens=[],
    )


def _combat_parsed(field_confidence: dict[str, float]) -> ParsedScreen:
    return ParsedScreen(
        "combat",
        [],
        Path("combat.png"),
        (1920, 1080),
        state_payload={
            "player": {"hp": 70, "max_hp": 80, "block": 0, "energy": 3, "turn": 1},
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
        field_confidence=field_confidence,
    )


def _make_step(parsed: ParsedScreen) -> GameStep:
    return game_step_from_parsed_screen(
        parsed=parsed,
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        captured_state=_captured_state(),
        source_type="fixture",
    )


def test_game_step_round_trips_new_entity_state() -> None:
    step = _game_step()

    decoded = GameStep.from_json(step.to_json())

    assert decoded == step
    assert decoded.state.player.character_resource["stance"] == "neutral"
    assert decoded.state.monsters[0].intent_damage == 11
    assert decoded.state.shop_items[0].card_id == "strike"
    assert decoded.state.event_options[0].label == "Take gold"
    assert decoded.state.rest_options[0].option_id == "rest"
    assert decoded.actions[2].legal is False
    assert decoded.observation.unknown_tokens == ["new_card"]
    assert decoded.observation.field_confidence == {"player.hp": 0.91, "cards": 0.88}


def test_game_step_rejects_empty_actions() -> None:
    with pytest.raises(ValueError, match="at least one action"):
        GameStep(
            state=_game_step().state,
            actions=[],
            chosen_action_id=None,
            outcome=None,
            observation=_game_step().observation,
            screenshot_path=Path("fixture.png"),
        )


def test_game_step_rejects_all_illegal_actions() -> None:
    with pytest.raises(ValueError, match="legal action"):
        GameStep(
            state=_game_step().state,
            actions=[ActionCandidate(action_type="pick_card", option_id="anger", legal=False)],
            chosen_action_id=None,
            outcome=None,
            observation=_game_step().observation,
            screenshot_path=Path("fixture.png"),
        )


def test_screen_option_states_validate_required_identifiers() -> None:
    with pytest.raises(ValueError, match="shop item_id"):
        ShopItemState("", "card", 75)
    with pytest.raises(ValueError, match="price"):
        ShopItemState("strike_plus", "card", -1)
    with pytest.raises(ValueError, match="event option_id"):
        EventOptionState("", "Take gold")
    with pytest.raises(ValueError, match="rest option_id"):
        RestOptionState("")


def test_action_identity_distinguishes_single_entity_action_types_and_targets() -> None:
    pick = ActionCandidate(action_type="pick_card", option_id="anger")
    play = ActionCandidate(action_type="play_card", source_card_id="strike")
    discard = ActionCandidate(action_type="discard_card", source_card_id="strike")
    first_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="jaw_worm")
    second_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="cultist")
    legacy_remove = ActionCandidate(action_type="remove_card", target_card_id="strike")
    legacy_defend_remove = ActionCandidate(action_type="remove_card", target_card_id="defend")
    slotted_remove = ActionCandidate(action_type="remove_card", target_card_id="strike", shop_item_id="remove_slot")

    assert pick.identity == "pick_card|option=anger"
    assert play.identity == "play_card|source_card=strike"
    assert discard.identity == "discard_card|source_card=strike"
    assert play.identity != discard.identity
    assert first_target.identity != second_target.identity
    assert first_target.identity == "play_card|source_card=strike|target_monster=jaw_worm"
    assert legacy_remove.identity == "remove_card|target_card=strike"
    assert legacy_defend_remove.identity == "remove_card|target_card=defend"
    assert slotted_remove.identity == "remove_card|target_card=strike"


def test_action_choice_aliases_resolve_unique_legacy_choices() -> None:
    actions = [
        ActionCandidate(action_type="pick_card", option_id="strike"),
        ActionCandidate(action_type="skip_reward", option_id="skip"),
        ActionCandidate(action_type="play_card", source_card_id="bash"),
        ActionCandidate(action_type="end_turn"),
    ]

    assert "pick_card:strike" in action_choice_aliases(actions[0])
    assert "skip" in action_choice_aliases(actions[1])
    assert "end_turn" in action_choice_aliases(actions[3])
    assert resolve_action_identity(actions, "pick_card:strike") == actions[0].identity
    assert resolve_action_identity(actions, "skip") == actions[1].identity
    assert resolve_action_identity(actions, "play_card:bash") == actions[2].identity
    assert resolve_action_identity(actions, "end_turn") == actions[3].identity


def test_action_choice_aliases_reject_ambiguous_or_illegal_choices() -> None:
    legal = ActionCandidate(action_type="play_card", source_card_id="strike")
    other_legal = ActionCandidate(action_type="discard_card", source_card_id="strike")
    illegal = ActionCandidate(action_type="pick_card", option_id="anger", legal=False)

    with pytest.raises(ValueError, match="ambiguous"):
        resolve_action_identity([legal, other_legal], "strike")
    with pytest.raises(ValueError, match="not legal"):
        resolve_action_identity([illegal], "anger")


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: PlayerState(hp=-1, max_hp=1, block=0, energy=0, turn=0), "player hp"),
        (lambda: PlayerState(hp=1, max_hp=1, block=-1, energy=0, turn=0), "player block"),
        (lambda: CardInstance("", "anger", "deck", False, None, None, "unknown", "unknown", []), "card instance"),
        (lambda: RelicState("", 0), "relic_id"),
        (lambda: RelicState("burning_blood", -1), "obtained_order"),
        (lambda: PotionState("", 0, False, True), "potion_id"),
        (lambda: PotionState("fire_potion", -1, False, True), "potion slot"),
        (
            lambda: MonsterState("", 0, 1, 1, 0, "attack", 1, 1, [], []),
            "monster_id",
        ),
        (
            lambda: MonsterState("jaw_worm", -1, 1, 1, 0, "attack", 1, 1, [], []),
            "monster numeric",
        ),
        (lambda: PathCandidate("", "elite", 1, 0, 0, 0, 0, 1), "path node"),
        (lambda: ActionCandidate(""), "action_type"),
    ],
)
def test_ml_entity_validation(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_step_factory_action_type_rejects_unknown_kind() -> None:
    assert _action_type("relic") == "pick_relic"
    assert _card_type(["attack"]) == "attack"
    assert _card_type([]) == "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        _action_type("boss")


def test_step_factory_keeps_state_when_no_reward_cards() -> None:
    captured = CapturedGameState(
        player=PlayerState(hp=1, max_hp=1, block=0, energy=0, turn=0),
        cards=[],
        relics=[],
        potions=[],
        monsters=[],
        path_candidates=[],
        missing_fields=[],
        unknown_tokens=[],
    )

    assert _state_with_reward_cards(captured, []) is captured


def test_step_factory_rejects_combat_when_required_field_confidence_is_low() -> None:
    parsed = _combat_parsed(
        {
            "player.hp": 0.95,
            "player.max_hp": 0.95,
            "player.block": 0.95,
            "player.energy": 0.59,
            "player.turn": 0.95,
            "cards": 0.95,
            "monsters": 0.95,
        }
    )

    with pytest.raises(PerceptionQualityError, match="player.energy"):
        _make_step(parsed)


def test_step_factory_rejects_map_when_required_path_candidates_are_missing() -> None:
    parsed = ParsedScreen(
        "map",
        [],
        Path("map.png"),
        (1920, 1080),
        state_payload={},
        missing_fields=["path_candidates"],
        field_confidence={},
    )

    with pytest.raises(PerceptionQualityError, match="path_candidates"):
        _make_step(parsed)


def test_step_factory_rejects_combat_when_required_field_confidence_is_missing() -> None:
    parsed = _combat_parsed(
        {
            "player.hp": 0.95,
            "player.max_hp": 0.95,
            "player.block": 0.95,
            "player.turn": 0.95,
            "cards": 0.95,
            "monsters": 0.95,
        }
    )

    with pytest.raises(PerceptionQualityError, match="player.energy:missing_confidence"):
        _make_step(parsed)


@pytest.mark.parametrize(
    ("kind", "payload", "missing_field", "confidence"),
    [
        (
            "shop",
            {"shop_items": [{"item_id": "strike_plus", "item_type": "card", "price": 75}]},
            "shop_items",
            {"shop_items": 0.59},
        ),
        (
            "event",
            {"event_options": [{"option_id": "take_gold", "label": "Take gold"}]},
            "event_options",
            {"event_options": 0.59},
        ),
        (
            "rest",
            {"rest_options": [{"option_id": "rest"}]},
            "rest_options",
            {"rest_options": 0.59},
        ),
    ],
)
def test_step_factory_rejects_shop_event_and_rest_when_required_options_are_low_confidence(
    kind: str,
    payload: dict[str, object],
    missing_field: str,
    confidence: dict[str, float],
) -> None:
    parsed = ParsedScreen(kind, [], Path(f"{kind}.png"), (1920, 1080), state_payload=payload, field_confidence=confidence)

    with pytest.raises(PerceptionQualityError, match=missing_field):
        _make_step(parsed)


@pytest.mark.parametrize(
    ("kind", "missing_field"),
    [
        ("shop", "shop_items"),
        ("event", "event_options"),
        ("rest", "rest_options"),
    ],
)
def test_step_factory_rejects_shop_event_and_rest_when_required_options_are_missing(
    kind: str,
    missing_field: str,
) -> None:
    parsed = ParsedScreen(
        kind,
        [],
        Path(f"{kind}.png"),
        (1920, 1080),
        state_payload={},
        missing_fields=[missing_field],
        field_confidence={},
    )

    with pytest.raises(PerceptionQualityError, match=missing_field):
        _make_step(parsed)


@pytest.mark.parametrize(
    ("kind", "payload", "missing_field"),
    [
        ("shop", {"shop_items": [{"item_id": "strike_plus", "item_type": "card", "price": 75}]}, "shop_items"),
        ("event", {"event_options": [{"option_id": "take_gold", "label": "Take gold"}]}, "event_options"),
        ("rest", {"rest_options": [{"option_id": "rest"}]}, "rest_options"),
    ],
)
def test_step_factory_rejects_shop_event_and_rest_when_required_confidence_is_missing(
    kind: str,
    payload: dict[str, object],
    missing_field: str,
) -> None:
    parsed = ParsedScreen(kind, [], Path(f"{kind}.png"), (1920, 1080), state_payload=payload)

    with pytest.raises(PerceptionQualityError, match=f"{missing_field}:missing_confidence"):
        _make_step(parsed)
