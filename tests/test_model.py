from pathlib import Path

import pytest
import torch

from sts2_tas.model import _torch_device, load_model, recommend, save_model, train_torch_model
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState


def _game_step(chosen: str, *, character: str = "ironclad") -> GameStep:
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character=character,
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=[
            ActionCandidate("pick_card", option_id="anger", legal=True),
            ActionCandidate("skip_reward", option_id="skip", legal=True),
        ],
        chosen_action_id=chosen,
        outcome=StepOutcome(victory=chosen == "anger", floor_reached=2, hp_remaining=70),
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )


def test_torch_recommend_scores_game_step_actions_and_rejects_bad_checkpoint(tmp_path: Path) -> None:
    model = train_torch_model(
        [_game_step("anger"), _game_step("skip")],
        "ironclad",
        epochs=1,
        batch_size=2,
        device="cpu",
        d_model=32,
        fusion_layers=1,
        ffn_dim=64,
    )
    bad_path = tmp_path / "bad.pt"
    torch.save({"format": "wrong"}, bad_path)

    result = recommend(model, _game_step("anger"))

    assert {candidate.action_id for candidate in result.candidates} == {"anger", "skip"}
    assert result.best.action_type in {"pick_card", "skip_reward"}
    with pytest.raises(ValueError, match="character"):
        recommend(model, _game_step("skip", character="silent"))
    with pytest.raises(ValueError, match="unsupported torch model format"):
        load_model(bad_path)


def test_torch_model_save_and_load_preserves_game_step_recommendation(tmp_path: Path) -> None:
    model = train_torch_model(
        [_game_step("anger"), _game_step("skip"), _game_step("anger"), _game_step("skip")],
        "ironclad",
        epochs=1,
        batch_size=2,
        device="cpu",
        d_model=32,
        fusion_layers=1,
        ffn_dim=64,
    )
    path = tmp_path / "model.pt"

    save_model(model, path)
    loaded = load_model(path)
    result = recommend(loaded, _game_step("anger"))

    assert result.best.action_id in {"anger", "skip"}
    assert len(result.candidates) == 2


def test_load_model_rejects_non_torch_model_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=".pt"):
        load_model(tmp_path / "model.bin")


def test_save_model_rejects_non_torch_model_files(tmp_path: Path) -> None:
    model = train_torch_model([_game_step("anger"), _game_step("skip")], character="ironclad", epochs=1, batch_size=2, device="cpu")

    with pytest.raises(ValueError, match=".pt"):
        save_model(model, tmp_path / "model.bin")


def test_torch_device_auto_prefers_available_accelerators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert _torch_device("auto") == "cuda"

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert _torch_device("auto") == "mps"

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert _torch_device("auto") == "cpu"
