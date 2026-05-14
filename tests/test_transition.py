from pathlib import Path

from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StructuredGameState
from sts2_tas.transition import acknowledge_transition


def _step(decision_context: str, action_id: str = "end_turn") -> GameStep:
    action = ActionCandidate(action_type=action_id)
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context=decision_context,
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=[action],
        chosen_action_id=action.identity,
        outcome=None,
        observation=ObservationQuality("fixture", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("screen.png"),
    )


def test_acknowledge_transition_splits_changed_noop_and_timeout() -> None:
    before = _step("combat")

    changed = acknowledge_transition(before, [_step("card_reward")], "end_turn")
    no_op = acknowledge_transition(before, [_step("combat")], "end_turn")
    timeout = acknowledge_transition(before, [], "end_turn")

    assert changed.status == "changed"
    assert changed.retry_recommended is False
    assert no_op.status == "no_op"
    assert no_op.retry_recommended is True
    assert timeout.status == "timeout"
    assert timeout.retry_recommended is True
