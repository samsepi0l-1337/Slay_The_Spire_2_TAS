from __future__ import annotations

import pytest

from sts2_tas.tas_movie import PhysicalInput, TasFrame, TasMovie


def _physical_inputs() -> list[PhysicalInput]:
    return [
        PhysicalInput(index=0, kind="key_tap", key="3"),
        PhysicalInput(index=1, kind="click", x=200, y=400, button="left"),
    ]


def _frame(frame: int) -> TasFrame:
    return TasFrame(
        frame=frame,
        semantic_action={"kind": "play_card", "card_instance": "hand-2-strike", "slot": 3, "target": "jaw_worm:0"},
        physical_input=_physical_inputs(),
        screen_hash=f"screen-{frame}",
        state_fingerprint=f"state-{frame}",
        decision_context="combat",
        source_policy="human",
        label_source="human",
        outcome_ref="run-1:victory" if frame == 2 else None,
    )


def test_tas_frame_round_trip_and_determinism_with_semantic_contract() -> None:
    frame = _frame(17)
    payload = frame.to_dict()
    decoded = TasFrame.from_dict(payload)

    assert decoded == frame
    assert TasFrame.from_json(frame.to_json()) == frame
    assert decoded.to_json() == frame.to_json()
    assert payload["semantic_action"]["kind"] == "play_card"
    assert payload["physical_input"][0] == {"index": 0, "kind": "key_tap", "key": "3"}
    assert payload["screen_hash"] == "screen-17"


def test_tas_movie_round_trip_and_frame_monotonicity_validation() -> None:
    movie = TasMovie(run_id="run-1", frames=[_frame(0), _frame(1), _frame(2)])
    round_trip = TasMovie.from_dict(movie.to_dict())

    assert round_trip == movie
    assert round_trip.to_json() == movie.to_json()

    with pytest.raises(ValueError, match="monotonic"):
        TasMovie(run_id="run-1", frames=[_frame(2), _frame(1)])


def test_tas_movie_prefix_hash_is_deterministic_and_progressive() -> None:
    frames = [_frame(0), _frame(1), _frame(2)]
    movie_a = TasMovie(run_id="run-1", frames=frames)
    movie_b = TasMovie(run_id="run-1", frames=[_frame(0), _frame(1), _frame(2)])

    assert movie_a.prefix_hash(1) == movie_b.prefix_hash(1)
    assert movie_a.prefix_hash(2) == movie_b.prefix_hash(2)
    assert movie_a.prefix_hash(3) == movie_b.prefix_hash(3)
    assert movie_a.prefix_hash(2) != movie_a.prefix_hash(3)


def test_physical_input_round_trip() -> None:
    physical_input = PhysicalInput(index=5, kind="key_tap", key="Space")
    wait_input = PhysicalInput(index=6, kind="wait", frames=3)

    assert PhysicalInput.from_dict(physical_input.to_dict()) == physical_input
    assert PhysicalInput.from_json(physical_input.to_json()) == physical_input
    assert wait_input.to_dict()["frames"] == 3


def test_physical_input_rejects_incomplete_inputs() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PhysicalInput(index=-1, kind="wait", frames=1)
    with pytest.raises(ValueError, match="unsupported"):
        PhysicalInput(index=0, kind="drag")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="key"):
        PhysicalInput(index=0, kind="key_tap")
    with pytest.raises(ValueError, match="click coordinates"):
        PhysicalInput(index=1, kind="click", x=10)
    with pytest.raises(ValueError, match="positive frames"):
        PhysicalInput(index=2, kind="wait", frames=0)


def test_tas_frame_rejects_missing_required_identity_fields() -> None:
    with pytest.raises(ValueError, match="frame index"):
        TasFrame(
            frame=-1,
            semantic_action=None,
            physical_input=[],
            screen_hash="screen",
            state_fingerprint="state",
            decision_context="combat",
            source_policy="human",
            label_source="human",
        )
    for field, message in [
        ("screen_hash", "screen_hash"),
        ("state_fingerprint", "state_fingerprint"),
        ("decision_context", "decision_context"),
        ("source_policy", "source_policy"),
        ("label_source", "label_source"),
    ]:
        kwargs = {
            "frame": 0,
            "semantic_action": None,
            "physical_input": [],
            "screen_hash": "screen",
            "state_fingerprint": "state",
            "decision_context": "combat",
            "source_policy": "human",
            "label_source": "human",
        }
        kwargs[field] = ""
        with pytest.raises(ValueError, match=message):
            TasFrame(**kwargs)


def test_tas_movie_rejects_missing_run_and_invalid_prefix_bounds(tmp_path) -> None:
    with pytest.raises(ValueError, match="run_id"):
        TasMovie(run_id="", frames=[])
    movie = TasMovie(run_id="run-1", frames=[_frame(0)])
    assert movie.prefix_hash() == movie.prefix_hash(1)
    with pytest.raises(ValueError, match="frame_count"):
        movie.prefix_hash(-1)
    with pytest.raises(ValueError, match="frame_count"):
        movie.prefix_hash(2)
    path = tmp_path / "movie.sts2movie"
    movie.write(path)
    assert TasMovie.load(path) == movie
