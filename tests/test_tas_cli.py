from __future__ import annotations

import json
from pathlib import Path

from sts2_tas import cli
from sts2_tas.ml_entities import ActionCandidate
from sts2_tas.tas_checkpoint import TasCheckpoint
from sts2_tas.tas_experience import TasExperience
from sts2_tas.tas_movie import PhysicalInput, TasFrame, TasMovie


def _frame(frame: int, *, outcome_ref: str | None = None) -> TasFrame:
    return TasFrame(
        frame=frame,
        semantic_action={"kind": "end_turn"} if frame else {"kind": "wait"},
        physical_input=[PhysicalInput(index=0, kind="key_tap", key="E")] if frame else [],
        screen_hash=f"screen-{frame}",
        state_fingerprint=f"state-{frame}",
        decision_context="combat",
        source_policy="verified_heuristic",
        label_source="verified_heuristic",
        outcome_ref=outcome_ref,
    )


def _victory_movie(path: Path) -> TasMovie:
    movie = TasMovie(run_id="run-1", game_version="0.105.1", branch="beta", frames=[_frame(0), _frame(1, outcome_ref="victory")])
    movie.write(path)
    return movie


def test_tas_probe_writes_passive_fallback_probe(tmp_path: Path) -> None:
    out = tmp_path / "probe.jsonl"

    assert cli.main(["tas-probe", "--target-process", "SlayTheSpire2", "--out", str(out), "--frames", "2"]) == 0

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [row["frame"] for row in rows] == [0, 1]
    assert {row["target_process"] for row in rows} == {"SlayTheSpire2"}
    assert {row["tas_grade"] for row in rows} == {False}
    assert {row["passive_only"] for row in rows} == {True}
    assert rows[0]["screen_hash"]


def test_tas_record_writes_empty_semantic_movie(tmp_path: Path) -> None:
    movie_path = tmp_path / "out.sts2movie"

    assert cli.main(["tas-record", "--target-process", "SlayTheSpire2", "--movie", str(movie_path), "--run-id", "run-2"]) == 0

    movie = TasMovie.load(movie_path)
    assert movie.run_id == "run-2"
    assert movie.target_process == "SlayTheSpire2"
    assert movie.frames == []


def test_tas_replay_verify_and_tas_verify_accept_victory_movie(tmp_path: Path, capsys) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)

    replay_code = cli.main(["tas-replay", "--movie", str(movie_path), "--target-process", "SlayTheSpire2", "--verify"])
    verify_code = cli.main(["tas-verify", "--movie", str(movie_path), "--runs", "5"])
    outputs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert replay_code == 0
    assert verify_code == 0
    assert outputs[0]["drift_count"] == 0
    assert outputs[1]["runs"] == 5
    assert outputs[1]["victories"] == 5
    assert outputs[1]["all_victory"] is True


def test_tas_search_validates_checkpoint_and_writes_prefix_movie(tmp_path: Path, capsys) -> None:
    movie_path = tmp_path / "run.sts2movie"
    movie = _victory_movie(movie_path)
    save_path = tmp_path / "save.bin"
    save_path.write_bytes(b"save-state")
    checkpoint = TasCheckpoint.from_movie_and_save(
        run_id="run-1",
        movie=movie,
        save_path=save_path,
        state_fingerprint="state-0",
        screen_hash="screen-0",
        movie_prefix_length=1,
    )
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(checkpoint.to_json(), encoding="utf-8")
    out = tmp_path / "best.sts2movie"

    assert cli.main(["tas-search", "--checkpoint", str(checkpoint_path), "--budget", "0", "--out", str(out)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["checkpoint_valid"] is True
    assert TasMovie.load(out).frames == [movie.frames[0]]


def test_train_verified_label_policy_reports_only_verified_tas_experience(tmp_path: Path, capsys) -> None:
    legal = ActionCandidate(action_type="end_turn", legal=True)
    rows = [
        TasExperience(
            behavior_policy="verified_heuristic",
            label_source="verified_heuristic",
            movie_frame=_frame(0),
            run_id="run-1",
            state_fingerprint="state-0",
            legal_actions=[legal],
            selected_action=legal,
            terminal_return=1.0,
            changed_ack=True,
        ),
        TasExperience(
            behavior_policy="model_self",
            label_source="model_self",
            movie_frame=_frame(1),
            run_id="run-1",
            state_fingerprint="state-1",
            legal_actions=[legal],
            selected_action=legal,
            terminal_return=1.0,
            changed_ack=True,
        ),
    ]
    dataset = tmp_path / "experience.jsonl"
    dataset.write_text("\n".join(row.to_json() for row in rows) + "\n", encoding="utf-8")

    assert cli.main(["train", "--dataset", str(dataset), "--label-policy", "verified"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report == {
        "label_policy": "verified",
        "rows": 2,
        "trainable_rows": 1,
        "excluded_rows": 1,
        "trained": False,
    }
