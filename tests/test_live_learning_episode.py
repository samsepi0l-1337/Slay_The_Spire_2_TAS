import argparse
from pathlib import Path
from types import SimpleNamespace

from sts2_tas import live_learning
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState


def test_gameplay_predicate_accepts_live_decision_contexts() -> None:
    assert live_learning._is_gameplay_step(SimpleNamespace(state=SimpleNamespace(decision_context="combat")))
    assert live_learning._is_gameplay_step(SimpleNamespace(state=SimpleNamespace(decision_context="map")))
    assert live_learning._is_gameplay_step(SimpleNamespace(state=SimpleNamespace(decision_context="card_reward")))
    assert live_learning._is_gameplay_step(SimpleNamespace(state=SimpleNamespace(decision_context="relic_choice")))
    assert not live_learning._is_gameplay_step(SimpleNamespace(state=SimpleNamespace(decision_context="main_menu")))


def test_append_episode_summary_ignores_non_terminal_rows(tmp_path: Path) -> None:
    state = live_learning._LoopState(episode_labeled_steps=1)
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
        ),
        actions=[ActionCandidate(action_type="end_turn")],
        chosen_action_id="end_turn",
        outcome=None,
        observation=ObservationQuality("fixture", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=tmp_path / "screen.png",
    )

    live_learning._append_episode_summary(
        argparse.Namespace(dataset=tmp_path / "dataset.jsonl", episodes_out=tmp_path / "episodes.jsonl"),
        state,
        step,
        "end_turn",
    )

    assert state.episode_labeled_steps == 1
    assert not (tmp_path / "episodes.jsonl").exists()


def test_append_episode_summary_resets_terminal_episode_without_output(tmp_path: Path) -> None:
    state = live_learning._LoopState(episode_labeled_steps=1)
    step = GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="game_over",
            player=PlayerState(hp=0, max_hp=80, block=0, energy=0, turn=0),
        ),
        actions=[ActionCandidate(action_type="restart_run", option_id="new_run")],
        chosen_action_id="restart_run|option=new_run",
        outcome=StepOutcome(victory=False, floor_reached=1, hp_remaining=0, terminal=True),
        observation=ObservationQuality("fixture", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=tmp_path / "screen.png",
    )

    labeled_steps = live_learning._append_episode_summary(
        argparse.Namespace(dataset=tmp_path / "missing-dataset.jsonl", episodes_out=None),
        state,
        step,
        "restart_run|option=new_run",
    )

    assert labeled_steps == 1
    assert state.episode_labeled_steps == 0
