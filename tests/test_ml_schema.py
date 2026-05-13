from pathlib import Path

import pytest

from sts2_tas.schema import (
    ActionCandidate,
    CardInstance,
    GameStep,
    MonsterState,
    ObservationQuality,
    PathCandidate,
    PlayerState,
    PotionState,
    RelicState,
    StepOutcome,
    StructuredGameState,
)
from sts2_tas.ml_entities import action_choice_aliases, resolve_action_identity
from sts2_tas.capture_state import CapturedGameState
from sts2_tas.step_factory import _action_type, _card_type, _state_with_reward_cards


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
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
        ),
        screenshot_path=Path("fixture.png"),
    )


def test_game_step_round_trips_new_entity_state() -> None:
    step = _game_step()

    decoded = GameStep.from_json(step.to_json())

    assert decoded == step
    assert decoded.state.player.character_resource["stance"] == "neutral"
    assert decoded.state.monsters[0].intent_damage == 11
    assert decoded.actions[2].legal is False
    assert decoded.observation.unknown_tokens == ["new_card"]


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


def test_action_identity_distinguishes_single_entity_action_types_and_targets() -> None:
    pick = ActionCandidate(action_type="pick_card", option_id="anger")
    play = ActionCandidate(action_type="play_card", source_card_id="strike")
    discard = ActionCandidate(action_type="discard_card", source_card_id="strike")
    first_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="jaw_worm")
    second_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="cultist")

    assert pick.identity == "pick_card|option=anger"
    assert play.identity == "play_card|source_card=strike"
    assert discard.identity == "discard_card|source_card=strike"
    assert play.identity != discard.identity
    assert first_target.identity != second_target.identity
    assert first_target.identity == "play_card|source_card=strike|target_monster=jaw_worm"


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
