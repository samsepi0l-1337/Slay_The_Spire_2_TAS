from __future__ import annotations

from pathlib import Path

from sts2_tas.ml_entities import ActionCandidate
from sts2_tas.tas_experience import TasExperience, supervised_training_experiences
from sts2_tas.tas_movie import TasFrame, TasMovie


def _frame() -> TasFrame:
    return TasFrame(
        frame=0,
        semantic_action={"kind": "pick_card", "option_id": "pick"},
        physical_input=[],
        screen_hash="screen-0",
        state_fingerprint="state-0",
        decision_context="card_reward",
        source_policy="human",
        label_source="human",
    )


def _movie(frame_label: str) -> TasMovie:
    return TasMovie(
        run_id="run-1",
        frames=[
            TasFrame(
                frame=0,
                semantic_action={"kind": "pick_card", "option_id": "pick"},
                physical_input=[],
                screen_hash=frame_label,
                state_fingerprint=frame_label,
                decision_context="card_reward",
                source_policy="human",
                label_source="human",
            )
        ],
    )


def _experience(
    *,
    label_source: str,
    behavior_policy: str = "human",
    terminal_return: float | None = 1.0,
    legal_selected: bool = True,
    changed_ack: bool = True,
    no_op: bool = False,
    drift_detected: bool = False,
    failure_reason: str | None = None,
) -> TasExperience:
    legal_action = ActionCandidate(action_type="pick_card", option_id="pick", legal=True)
    illegal_action = ActionCandidate(action_type="end_turn", legal=False)
    selected_action = legal_action if legal_selected else illegal_action
    return TasExperience(
        behavior_policy=behavior_policy,
        label_source=label_source,
        movie_frame=_frame(),
        run_id="run-1",
        state_fingerprint="state-0",
        legal_actions=[legal_action, illegal_action],
        selected_action=selected_action,
        terminal_return=terminal_return,
        changed_ack=changed_ack,
        no_op=no_op,
        drift_detected=drift_detected,
        failure_reason=failure_reason,
    )


def test_tas_experience_round_trip() -> None:
    experience = _experience(label_source="human", terminal_return=1.0, behavior_policy="human")
    payload = experience.to_dict()
    decoded = TasExperience.from_dict(payload)

    assert decoded == experience
    assert decoded.to_json() == experience.to_json()


def test_supervised_experience_filter_includes_allowed_sources_and_excludes_rejected() -> None:
    samples = [
        _experience(label_source="human", behavior_policy="human", terminal_return=1.0),
        _experience(label_source="search_success", behavior_policy="search", terminal_return=0.0),
        _experience(label_source="verified_heuristic", behavior_policy="heuristic", terminal_return=0.25),
        _experience(label_source="model_self", behavior_policy="model_self", terminal_return=0.4),
        _experience(label_source="failed_rollout", behavior_policy="search", terminal_return=0.9),
        _experience(label_source="no_op", behavior_policy="no_op", terminal_return=0.1),
        _experience(label_source="drift", behavior_policy="drift", terminal_return=0.1),
        _experience(label_source="illegal", behavior_policy="human", terminal_return=0.5, legal_selected=False),
        _experience(label_source="no_terminal", behavior_policy="human", terminal_return=None),
        _experience(label_source="human", behavior_policy="human", terminal_return=1.0, changed_ack=False),
        _experience(label_source="human", behavior_policy="human", terminal_return=1.0, no_op=True),
        _experience(label_source="human", behavior_policy="human", terminal_return=1.0, drift_detected=True),
        _experience(label_source="human", behavior_policy="human", terminal_return=1.0, failure_reason="timeout"),
    ]
    selected = supervised_training_experiences(samples)

    assert [exp.label_source for exp in selected] == [
        "human",
        "search_success",
        "verified_heuristic",
    ]


def test_tas_experience_movie_round_trip_uses_frame_index_for_identity() -> None:
    movie = _movie("screen-2")
    experience = TasExperience(
        behavior_policy="human",
        label_source="human",
        movie_frame=movie.frames[0],
        run_id="run-1",
        state_fingerprint="state-0",
        legal_actions=[ActionCandidate(action_type="pick_card", option_id="pick", legal=True)],
        selected_action=ActionCandidate(action_type="pick_card", option_id="pick", legal=True),
        terminal_return=1.0,
        changed_ack=True,
    )

    assert experience.to_dict()["movie_frame"]["frame"] == 0
