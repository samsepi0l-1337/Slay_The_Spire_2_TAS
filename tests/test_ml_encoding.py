from pathlib import Path

import pytest

from sts2_tas.catalog import EntityCatalog
from sts2_tas.encoding import TOKEN_TYPE_IDS, _pad_numeric, encode_game_step
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
from sts2_tas.torch_dataset import GameStepTorchDataset, collate_encoded_steps


def _step(chosen: str = "anger") -> GameStep:
    actions = [
        ActionCandidate(action_type="pick_card", option_id="anger", legal=True),
        ActionCandidate(action_type="skip_reward", option_id="skip", legal=True),
        ActionCandidate(action_type="play_card", source_card_id="strike", legal=False),
    ]
    aliases = {"anger": actions[0].identity, "skip": actions[1].identity, "strike": actions[2].identity}
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=actions,
        chosen_action_id=aliases.get(chosen, chosen),
        outcome=StepOutcome(victory=True, floor_reached=2, hp_remaining=70),
        observation=ObservationQuality(
            source_type="screen",
            ocr_confidence=1.0,
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
        ),
        screenshot_path=Path("fixture.png"),
    )


def test_catalog_maps_unknown_entities_to_stable_category_token() -> None:
    catalog = EntityCatalog(version="test-catalog")

    first = catalog.id_for("card", "unseen_card")
    second = catalog.id_for("card", "another_unseen_card")

    assert catalog.version == "test-catalog"
    assert first == second
    assert first == catalog.id_for("card", "unseen_card")

    with pytest.raises(ValueError, match="unsupported catalog category"):
        catalog.id_for("unsupported", "x")


def test_encode_game_step_creates_action_mask_and_label_index() -> None:
    step = _step()
    catalog = EntityCatalog.from_steps([step], version="test-catalog")

    encoded = encode_game_step(step, catalog)

    assert len(encoded.token_ids) == len(encoded.token_types) == len(encoded.numeric_features)
    assert encoded.token_types[0] == TOKEN_TYPE_IDS["GLOBAL"]
    assert encoded.action_mask == [True, True, False]
    assert encoded.label_action_index == 0
    assert encoded.outcome_value == 1.0
    assert encoded.outcome_mask is True
    assert encoded.action_positions[0] < len(encoded.token_ids)


def test_collate_encoded_steps_pads_tokens_and_actions() -> None:
    catalog = EntityCatalog.from_steps([_step(), _step("skip")], version="test-catalog")
    encoded = [encode_game_step(_step(), catalog), encode_game_step(_step("skip"), catalog)]

    batch = collate_encoded_steps(encoded)

    assert batch["token_ids"].shape[0] == 2
    assert batch["numeric_features"].shape[:2] == batch["token_ids"].shape
    assert batch["action_positions"].shape == batch["action_mask"].shape
    assert batch["labels"].tolist() == [0, 1]
    assert batch["outcome_mask"].tolist() == [True, True]


def test_encoding_covers_optional_entity_groups_and_error_paths() -> None:
    full_step = GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="combat",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
            cards=[
                CardInstance(
                    "deck-strike",
                    "strike",
                    "deck",
                    True,
                    None,
                    None,
                    "attack",
                    "basic",
                    ["attack"],
                    retain=True,
                )
            ],
            relics=[RelicState("burning_blood", 0, counter=None, cooldown=None, activated_this_combat=True)],
            potions=[PotionState("fire_potion", 0, True, True)],
            monsters=[MonsterState("jaw_worm", 0, 10, 40, 0, "attack", 7, 1, [], [])],
            path_candidates=[PathCandidate("n1", "elite", 1, 1, 0, 0, 0, 5, True)],
        ),
        actions=[ActionCandidate(action_type="end_turn", legal=True)],
        chosen_action_id="end_turn",
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )
    catalog = EntityCatalog.from_steps([full_step], version="test-catalog")

    encoded = encode_game_step(full_step, catalog)

    assert encoded.outcome_value == 0.0
    assert encoded.outcome_mask is False
    assert TOKEN_TYPE_IDS["CARD"] in encoded.token_types
    assert TOKEN_TYPE_IDS["RELIC"] in encoded.token_types
    assert TOKEN_TYPE_IDS["POTION"] in encoded.token_types
    assert TOKEN_TYPE_IDS["MONSTER"] in encoded.token_types
    assert TOKEN_TYPE_IDS["PATH"] in encoded.token_types
    assert _pad_numeric([float(index) for index in range(20)]) == [float(index) for index in range(16)]

    with pytest.raises(ValueError, match="chosen_action_id"):
        encode_game_step(
            GameStep(full_step.state, full_step.actions, None, None, full_step.observation, full_step.screenshot_path),
            catalog,
        )
    with pytest.raises(ValueError, match="not present"):
        encode_game_step(
            GameStep(full_step.state, full_step.actions, "missing", None, full_step.observation, full_step.screenshot_path),
            catalog,
        )
    with pytest.raises(ValueError, match="chosen action must be legal"):
        encode_game_step(
            GameStep(
                full_step.state,
                [
                    ActionCandidate(action_type="end_turn", legal=False),
                    ActionCandidate(action_type="skip_reward", option_id="skip", legal=True),
                ],
                "end_turn",
                None,
                full_step.observation,
                full_step.screenshot_path,
            ),
            catalog,
        )


def test_encoding_keeps_targeted_combat_actions_distinct() -> None:
    first = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="jaw_worm")
    second = ActionCandidate(action_type="play_card", source_card_id="strike", target_monster_id="cultist")
    step = GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="combat",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
            monsters=[
                MonsterState("jaw_worm", 0, 10, 40, 0, "attack", 7, 1, [], []),
                MonsterState("cultist", 1, 12, 48, 0, "buff", 0, 0, [], []),
            ],
        ),
        actions=[first, second],
        chosen_action_id=second.identity,
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )
    catalog = EntityCatalog.from_steps([step], version="test-catalog")

    encoded = encode_game_step(step, catalog)

    assert first.identity != second.identity
    assert encoded.label_action_index == 1
    assert encoded.token_ids[encoded.action_positions[0]] != encoded.token_ids[encoded.action_positions[1]]


def test_encoding_includes_gold_from_player_character_resource() -> None:
    action = ActionCandidate(action_type="skip_reward", option_id="skip", legal=True)
    step = GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(
                hp=70,
                max_hp=80,
                block=0,
                energy=3,
                turn=1,
                character_resource={"gold": 99},
            ),
        ),
        actions=[action],
        chosen_action_id=action.identity,
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )
    catalog = EntityCatalog.from_steps([step], version="test-catalog")

    encoded = encode_game_step(step, catalog)
    player_index = encoded.token_types.index(TOKEN_TYPE_IDS["PLAYER"])

    assert encoded.numeric_features[player_index][14] == 99.0


def test_torch_dataset_rejects_unlabeled_steps() -> None:
    step = _step(chosen="anger")
    unlabeled = GameStep(step.state, step.actions, None, step.outcome, step.observation, step.screenshot_path)

    with pytest.raises(ValueError, match="at least one labeled"):
        GameStepTorchDataset([unlabeled])
