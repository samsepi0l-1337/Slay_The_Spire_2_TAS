from pathlib import Path

import pytest
import torch

from sts2_tas.model import _torch_device, load_model, recommend, save_model, train_model, train_torch_model
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState
from sts2_tas.schema import ChoiceOption, DecisionChoice, DecisionSnapshot


def _snapshot(choice: DecisionChoice, relics: list[str], options: list[ChoiceOption]) -> DecisionSnapshot:
    return DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=1,
        floor=6,
        deck=["strike", "defend", "bash"],
        relics=relics,
        hp=55,
        gold=80,
        options=options,
        chosen=choice,
        skipped=choice.action == "skip",
        screenshot_path=Path("fixture.png"),
    )


def test_model_recommends_memorized_best_candidate() -> None:
    options = [
        ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
        ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
    ]
    model = train_model(
        [
            _snapshot(DecisionChoice(action="pick", option_id="anger"), ["burning_blood"], options),
            _snapshot(DecisionChoice(action="skip"), ["tiny_house"], options),
        ],
        character="ironclad",
    )

    result = recommend(model, _snapshot(DecisionChoice(action="pick", option_id="anger"), ["burning_blood"], options))

    assert result.best.option_id == "anger"
    assert result.best.action == "pick"
    assert result.best.score >= result.candidates[1].score


def test_model_save_and_load_preserves_recommendation(tmp_path: Path) -> None:
    options = [
        ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
        ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
    ]
    model = train_model(
        [
            _snapshot(DecisionChoice(action="pick", option_id="anger"), ["burning_blood"], options),
            _snapshot(DecisionChoice(action="skip"), ["tiny_house"], options),
        ],
        character="ironclad",
    )
    path = tmp_path / "model.joblib"

    save_model(model, path)
    loaded = load_model(path)

    assert recommend(loaded, _snapshot(DecisionChoice(action="skip"), ["tiny_house"], options)).best.action == "skip"


def test_train_model_rejects_single_class_data() -> None:
    options = [ChoiceOption(id="anger", name="Anger", kind="card", tags=[])]

    with pytest.raises(ValueError, match="at least two classes"):
        train_model([_snapshot(DecisionChoice(action="pick", option_id="anger"), [], options)], character="ironclad")


def test_recommend_rejects_character_mismatch() -> None:
    options = [
        ChoiceOption(id="anger", name="Anger", kind="card", tags=["attack"]),
        ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
    ]
    model = train_model(
        [
            _snapshot(DecisionChoice(action="pick", option_id="anger"), ["burning_blood"], options),
            _snapshot(DecisionChoice(action="skip"), ["tiny_house"], options),
        ],
        character="ironclad",
    )
    silent_snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="silent",
        ascension=1,
        floor=6,
        deck=[],
        relics=[],
        hp=55,
        gold=80,
        options=options,
        chosen=DecisionChoice(action="skip"),
        skipped=True,
        screenshot_path=Path("fixture.png"),
    )

    with pytest.raises(ValueError, match="character"):
        recommend(model, silent_snapshot)


def _game_step(chosen: str) -> GameStep:
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
        actions=[
            ActionCandidate("pick_card", option_id="anger", legal=True),
            ActionCandidate("skip_reward", option_id="skip", legal=True),
        ],
        chosen_action_id=chosen,
        outcome=StepOutcome(victory=chosen == "anger", floor_reached=2, hp_remaining=70),
        observation=ObservationQuality("legacy", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )


def test_torch_recommend_rejects_character_mismatch_and_invalid_checkpoint(tmp_path: Path) -> None:
    model = train_torch_model([_game_step("anger"), _game_step("skip")], "ironclad", epochs=1, batch_size=2, device="cpu", d_model=32, fusion_layers=1, ffn_dim=64)
    silent_snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="silent",
        ascension=1,
        floor=6,
        deck=[],
        relics=[],
        hp=55,
        gold=80,
        options=[ChoiceOption(id="skip", name="Skip", kind="skip", tags=[])],
        chosen=DecisionChoice(action="skip"),
        skipped=True,
        screenshot_path=Path("fixture.png"),
    )
    bad_path = tmp_path / "bad.pt"
    torch.save({"format": "wrong"}, bad_path)

    with pytest.raises(ValueError, match="character"):
        recommend(model, silent_snapshot)
    with pytest.raises(ValueError, match="unsupported torch model format"):
        load_model(bad_path)


def test_torch_device_auto_prefers_available_accelerators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert _torch_device("auto") == "cuda"

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert _torch_device("auto") == "mps"

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert _torch_device("auto") == "cpu"
