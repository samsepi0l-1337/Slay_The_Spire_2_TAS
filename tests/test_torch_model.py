from pathlib import Path

import torch

from sts2_tas.catalog import EntityCatalog
from sts2_tas.encoding import NUMERIC_FEATURE_DIM, TOKEN_TYPE_IDS, encode_game_step
from sts2_tas.model import load_model, recommend, save_model, train_torch_model
from sts2_tas.schema import (
    ActionCandidate,
    GameStep,
    ObservationQuality,
    PlayerState,
    StepOutcome,
    StructuredGameState,
)
from sts2_tas.torch_dataset import collate_encoded_steps
from sts2_tas.torch_model import EntityTransformerActorCritic


def _step(chosen: str, victory: bool) -> GameStep:
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
            player=PlayerState(hp=70 if victory else 10, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=actions,
        chosen_action_id=aliases.get(chosen, chosen),
        outcome=StepOutcome(victory=victory, floor_reached=2, hp_remaining=70 if victory else 10),
        observation=ObservationQuality(
            source_type="screen",
            ocr_confidence=1.0,
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
        ),
        screenshot_path=Path("fixture.png"),
    )


def test_entity_transformer_masks_illegal_actions() -> None:
    step = _step("anger", victory=True)
    catalog = EntityCatalog.from_steps([step], version="test-catalog")
    batch = collate_encoded_steps([encode_game_step(step, catalog)])
    model = EntityTransformerActorCritic(
        vocab_size=catalog.size,
        token_type_count=len(TOKEN_TYPE_IDS),
        numeric_dim=NUMERIC_FEATURE_DIM,
        d_model=32,
        heads=4,
        fusion_layers=1,
        ffn_dim=64,
        dropout=0.0,
    )

    output = model(**{key: value for key, value in batch.items() if key not in {"labels", "outcome_values", "outcome_mask"}})

    assert output.policy_logits.shape == (1, 3)
    assert output.value.shape == (1,)
    assert torch.isneginf(output.policy_logits[0, 2])


def test_torch_model_save_load_preserves_recommendation(tmp_path: Path) -> None:
    model = train_torch_model(
        [_step("anger", True), _step("skip", False), _step("anger", True), _step("skip", False)],
        character="ironclad",
        epochs=2,
        batch_size=2,
        device="cpu",
        d_model=32,
        fusion_layers=1,
        ffn_dim=64,
    )
    path = tmp_path / "model.pt"

    save_model(model, path)
    loaded = load_model(path)
    result = recommend(loaded, _step("anger", True))

    assert result.best.option_id in {"anger", "skip"}
    assert len(result.candidates) == 2
