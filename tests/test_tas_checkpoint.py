from __future__ import annotations

from pathlib import Path

import pytest

from sts2_tas.tas_checkpoint import TasCheckpoint
from sts2_tas.tas_movie import TasFrame, TasMovie


def _movie() -> TasMovie:
    return TasMovie(
        run_id="run-1",
        frames=[
            TasFrame(
                frame=0,
                semantic_action={"kind": "wait"},
                physical_input=[],
                screen_hash="screen-0",
                state_fingerprint="state-0",
                decision_context="combat",
                source_policy="human",
                label_source="human",
            ),
            TasFrame(
                frame=1,
                semantic_action={"kind": "end_turn"},
                physical_input=[],
                screen_hash="screen-1",
                state_fingerprint="state-1",
                decision_context="combat",
                source_policy="human",
                label_source="human",
            ),
        ],
    )


def _write_save(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def test_tas_checkpoint_round_trips_and_verifies_save_hash(tmp_path: Path) -> None:
    save_path = tmp_path / "game-save.bin"
    _write_save(save_path, b"state by bytes")
    movie = _movie()

    checkpoint = TasCheckpoint.from_movie_and_save(
        run_id="run-1",
        movie=movie,
        save_path=save_path,
        state_fingerprint="state-1",
        screen_hash="screen-1",
        movie_prefix_length=2,
    )

    decoded = TasCheckpoint.from_dict(checkpoint.to_dict())

    assert decoded == checkpoint
    assert decoded.to_json() == checkpoint.to_json()
    assert decoded.validate_save(save_path=save_path)
    assert decoded.validate_screen_state_fingerprints()


def test_tas_checkpoint_detects_tampered_save_hash(tmp_path: Path) -> None:
    save_path = tmp_path / "game-save.bin"
    _write_save(save_path, b"state by bytes")
    checkpoint = TasCheckpoint.from_movie_and_save(
        run_id="run-1",
        movie=_movie(),
        save_path=save_path,
        state_fingerprint="state-1",
        screen_hash="screen-1",
        movie_prefix_length=2,
    )
    _write_save(save_path, b"changed bytes")

    assert checkpoint.validate_save(save_path=save_path) is False


def test_tas_checkpoint_rejects_prefix_hash_mismatch_for_validation() -> None:
    movie = _movie()
    real_hash = "a" * 64
    empty = TasCheckpoint(
        run_id="run-1",
        movie=movie,
        save_path=Path("missing.bin"),
        save_hash=real_hash,
        movie_prefix_hash="bad-hash",
        movie_prefix_length=2,
        state_fingerprint="state-1",
        screen_hash="screen-1",
    )

    assert empty.validate_movie_prefix_hash() is False


def test_tas_checkpoint_default_prefix_json_and_missing_save(tmp_path: Path) -> None:
    save_path = tmp_path / "game-save.bin"
    _write_save(save_path, b"state by bytes")
    checkpoint = TasCheckpoint.from_movie_and_save(
        run_id="run-1",
        movie=_movie(),
        save_path=save_path,
        state_fingerprint="state-1",
        screen_hash="screen-1",
    )

    decoded = TasCheckpoint.from_json(checkpoint.to_json())

    assert decoded.movie_prefix_length == 2
    assert decoded.validate_save(tmp_path / "missing.bin") is False


def test_tas_checkpoint_rejects_invalid_contract_fields() -> None:
    movie = _movie()
    base = {
        "run_id": "run-1",
        "movie": movie,
        "save_path": Path("save.bin"),
        "save_hash": "a" * 64,
        "movie_prefix_hash": movie.prefix_hash(1),
        "movie_prefix_length": 1,
        "state_fingerprint": "state-0",
        "screen_hash": "screen-0",
    }
    invalid_cases = [
        ({"run_id": ""}, "run_id"),
        ({"movie_prefix_length": -1}, "movie_prefix_length"),
        ({"movie_prefix_length": 3}, "movie_prefix_length"),
        ({"save_hash": "bad"}, "save_hash"),
        ({"movie_prefix_hash": ""}, "movie_prefix_hash"),
        ({"screen_hash": ""}, "screen_hash"),
        ({"state_fingerprint": ""}, "state_fingerprint"),
    ]

    for overrides, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            TasCheckpoint(**(base | overrides))


def test_tas_checkpoint_rejects_empty_prefix_screen_state_validation() -> None:
    movie = _movie()
    checkpoint = TasCheckpoint(
        run_id="run-1",
        movie=movie,
        save_path=Path("save.bin"),
        save_hash="a" * 64,
        movie_prefix_hash=movie.prefix_hash(0),
        movie_prefix_length=0,
        state_fingerprint="state-0",
        screen_hash="screen-0",
    )

    assert checkpoint.validate_screen_state_fingerprints() is False
