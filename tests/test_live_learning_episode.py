import argparse
from pathlib import Path

from sts2_tas import live_learning
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StructuredGameState


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
