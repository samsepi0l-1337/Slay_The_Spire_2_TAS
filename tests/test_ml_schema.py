from pathlib import Path

import pytest

from sts2_tas.schema import (
    ActionCandidate,
    CardInstance,
    ChoiceOption,
    DecisionChoice,
    DecisionSnapshot,
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


def test_legacy_snapshot_migrates_to_reward_game_step() -> None:
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=2,
        floor=3,
        deck=["strike", "defend"],
        relics=["burning_blood"],
        hp=70,
        gold=99,
        options=[
            ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
            ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
        ],
        chosen=DecisionChoice(action="pick", option_id="anger"),
        skipped=False,
        screenshot_path=Path("reward.png"),
    )

    step = GameStep.from_legacy_snapshot(snapshot, catalog_version="test-catalog")

    assert step.state.decision_context == "card_reward"
    assert [card.card_id for card in step.state.cards] == ["strike", "defend"]
    assert [relic.relic_id for relic in step.state.relics] == ["burning_blood"]
    assert [action.option_id for action in step.actions] == ["anger", "skip"]
    assert step.chosen_action_id == "anger"
    assert step.observation.catalog_version == "test-catalog"


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


def test_action_identity_distinguishes_targets_without_breaking_simple_ids() -> None:
    pick = ActionCandidate(action_type="pick_card", option_id="anger")
    source_only = ActionCandidate(action_type="play_card", source_card_id="strike")
    first_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="jaw_worm")
    second_target = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="cultist")

    assert pick.identity == "anger"
    assert source_only.identity == "strike"
    assert first_target.identity != second_target.identity
    assert first_target.identity == "source_card=strike|target_monster=jaw_worm"


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


def test_legacy_snapshot_migrates_relic_and_unknown_contexts() -> None:
    relic_snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=1,
        gold=0,
        options=[ChoiceOption(id="relic_1", name="Relic", kind="relic", tags=[])],
        chosen=None,
        skipped=False,
        screenshot_path=Path("relic.png"),
    )
    relic_skip_without_option = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=1,
        gold=0,
        options=[ChoiceOption(id="relic_1", name="Relic", kind="relic", tags=[])],
        chosen=DecisionChoice(action="skip"),
        skipped=True,
        screenshot_path=Path("relic-skip.png"),
    )
    unknown_snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=1,
        gold=0,
        options=[ChoiceOption(id="skip", name="Skip", kind="skip", tags=[])],
        chosen=DecisionChoice(action="skip"),
        skipped=True,
        screenshot_path=Path("unknown.png"),
    )

    relic_step = GameStep.from_legacy_snapshot(relic_snapshot, catalog_version="test")
    relic_skip_step = GameStep.from_legacy_snapshot(relic_skip_without_option, catalog_version="test")
    unknown_step = GameStep.from_legacy_snapshot(unknown_snapshot, catalog_version="test")

    assert relic_step.state.decision_context == "relic_reward"
    assert relic_step.chosen_action_id is None
    assert relic_skip_step.chosen_action_id == "skip"
    assert unknown_step.state.decision_context == "unknown"
    assert unknown_step.chosen_action_id == "skip"
