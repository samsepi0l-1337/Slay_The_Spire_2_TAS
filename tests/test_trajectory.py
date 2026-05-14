import json
from pathlib import Path

import pytest

from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState
from sts2_tas.trajectory import (
    EpisodeState,
    TrajectoryStep,
    load_trajectory_steps,
    supervised_training_steps,
    value_target_for_step,
    write_trajectory_steps,
)


def _game_step(label_source: str = "human", outcome: StepOutcome | None = None) -> GameStep:
    action = ActionCandidate(action_type="pick_card", option_id="anger", legal=True)
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=3,
            decision_context="card_reward",
            player=PlayerState(hp=44, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=[action, ActionCandidate(action_type="skip_reward", option_id="skip", legal=True)],
        chosen_action_id=action.identity,
        outcome=outcome or StepOutcome(victory=False, floor_reached=3, hp_remaining=44, immediate_reward=0.2),
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
        label_source=label_source,
    )


def test_trajectory_step_round_trips_dict_json_and_jsonl(tmp_path: Path) -> None:
    before = EpisodeState(run_id="run-1", seed=7, game_version="0.105.1", floor=3, room_type="combat", turn_index=2)
    after = EpisodeState(run_id="run-1", seed=7, game_version="0.105.1", floor=4, room_type="reward", turn_index=0)
    selected = ActionCandidate(action_type="pick_card", option_id="anger", legal=True)
    step = TrajectoryStep(
        run_id="run-1",
        seed=7,
        game_version="0.105.1",
        floor=3,
        room_type="combat",
        turn_index=2,
        state_before=before,
        legal_actions=[selected, ActionCandidate(action_type="skip_reward", option_id="skip", legal=True)],
        selected_action=selected,
        state_after=after,
        reward=1.25,
        terminal=False,
        label_source="search",
    )
    path = tmp_path / "trajectory.jsonl"

    decoded = TrajectoryStep.from_json(step.to_json())
    write_trajectory_steps(path, [step])

    assert decoded == step
    assert TrajectoryStep.from_dict(step.to_dict()) == step
    assert load_trajectory_steps(path) == [step]
    assert json.loads(path.read_text(encoding="utf-8"))["state_before"]["run_id"] == "run-1"


def test_game_step_label_source_is_backward_compatible_and_filters_training_rows() -> None:
    legacy = _game_step().to_dict()
    legacy.pop("label_source")
    rows = [
        GameStep.from_dict(legacy),
        _game_step("search"),
        _game_step("heuristic"),
        _game_step("model_shadow"),
        _game_step("model_self"),
    ]

    assert rows[0].label_source == "human"
    assert [step.label_source for step in supervised_training_steps(rows)] == ["human", "search", "heuristic"]


def test_value_target_prefers_richer_reward_signals_before_victory() -> None:
    explicit = _game_step(outcome=StepOutcome(False, 1, 1, value_target=0.42))
    returned = _game_step(outcome=StepOutcome(False, 1, 1, discounted_return=0.7))
    shaped = _game_step(outcome=StepOutcome(True, 10, 50, immediate_reward=0.25, terminal=False))
    fallback = _game_step(outcome=StepOutcome(True, 0, 0, immediate_reward=0.0, terminal=False))

    assert value_target_for_step(explicit) == 0.42
    assert value_target_for_step(returned) == 0.7
    assert value_target_for_step(shaped) != 1.0
    assert value_target_for_step(fallback) == 1.0


def test_trajectory_and_label_source_validation_fail_closed() -> None:
    state = EpisodeState("run-1", 7, "0.105.1", 1, "combat", 0)
    action = ActionCandidate(action_type="end_turn")

    with pytest.raises(ValueError, match="unsupported label_source"):
        _game_step("bad-source")
    with pytest.raises(ValueError, match="legal_actions"):
        TrajectoryStep("run-1", 7, "0.105.1", 1, "combat", 0, state, [], action, state, 0.0, False)
    with pytest.raises(ValueError, match="selected_action"):
        TrajectoryStep(
            "run-1",
            7,
            "0.105.1",
            1,
            "combat",
            0,
            state,
            [ActionCandidate(action_type="pick_card", option_id="anger")],
            action,
            state,
            0.0,
            False,
        )
    with pytest.raises(ValueError, match="unsupported label_source"):
        TrajectoryStep("run-1", 7, "0.105.1", 1, "combat", 0, state, [action], action, state, 0.0, False, "bad-source")


def test_value_target_covers_empty_and_terminal_win_signal() -> None:
    no_outcome = GameStep(
        state=_game_step().state,
        actions=_game_step().actions,
        chosen_action_id=_game_step().chosen_action_id,
        outcome=None,
        observation=_game_step().observation,
        screenshot_path=Path("fixture.png"),
    )
    terminal_win = _game_step(outcome=StepOutcome(True, 60, 80, immediate_reward=1.0, terminal=True))

    assert value_target_for_step(no_outcome) == 0.0
    assert value_target_for_step(terminal_win) == 1.0
