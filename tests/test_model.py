from pathlib import Path

import pytest

from sts2_tas.model import load_model, recommend, save_model, train_model
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
