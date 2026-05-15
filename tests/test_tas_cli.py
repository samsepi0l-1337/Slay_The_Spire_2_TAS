from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts2_tas import cli
from sts2_tas.ml_entities import ActionCandidate
from sts2_tas.tas_checkpoint import TasCheckpoint
from sts2_tas.tas_experience import TasExperience
from sts2_tas.tas_movie import PhysicalInput, TasFrame, TasMovie
from sts2_tas.tas_replay import (
    DefaultLiveReplayObserver,
    automation_action_from_physical_input,
    replay_movie_live,
)


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


def test_tas_probe_rejects_non_positive_frame_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frames"):
        cli.main(["tas-probe", "--target-process", "SlayTheSpire2", "--out", str(tmp_path / "probe.jsonl"), "--frames", "0"])


def test_tas_record_writes_empty_semantic_movie(tmp_path: Path) -> None:
    movie_path = tmp_path / "out.sts2movie"

    assert cli.main(["tas-record", "--target-process", "SlayTheSpire2", "--movie", str(movie_path), "--run-id", "run-2"]) == 0

    movie = TasMovie.load(movie_path)
    assert movie.run_id == "run-2"
    assert movie.target_process == "SlayTheSpire2"
    assert movie.frames == []


def test_tas_record_live_rejects_non_positive_frame_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frames"):
        cli.main(
            [
                "tas-record",
                "--target-process",
                "SlayTheSpire2",
                "--movie",
                str(tmp_path / "recorded.sts2movie"),
                "--live",
                "--frames",
                "0",
            ]
        )


def test_tas_replay_verify_and_tas_verify_accept_victory_movie(tmp_path: Path, capsys) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)

    replay_code = cli.main(["tas-replay", "--movie", str(movie_path), "--target-process", "SlayTheSpire2", "--verify"])
    verify_code = cli.main(["tas-verify", "--movie", str(movie_path), "--runs", "5"])
    outputs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert replay_code == 0
    assert verify_code == 0
    assert outputs[0]["drift_count"] == 0
    assert outputs[0]["acceptance_source"] == "static_movie"
    assert outputs[0]["tas_grade"] is False
    assert outputs[1]["runs"] == 5
    assert outputs[1]["victories"] == 5
    assert outputs[1]["all_victory"] is True
    assert outputs[1]["acceptance_source"] == "static_movie"
    assert outputs[1]["tas_grade"] is False


def test_tas_verify_rejects_non_positive_runs(tmp_path: Path) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)

    with pytest.raises(ValueError, match="runs"):
        cli.main(["tas-verify", "--movie", str(movie_path), "--runs", "0"])


def test_tas_replay_reports_target_process_mismatch(tmp_path: Path, capsys) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)

    assert cli.main(["tas-replay", "--movie", str(movie_path), "--target-process", "OtherProcess", "--verify"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["target_window_mismatch_count"] == 1


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
    assert report["acceptance_eligible"] is True
    assert TasMovie.load(out).frames == [movie.frames[0]]


def test_tas_search_invalid_checkpoint_does_not_write_prefix_movie(tmp_path: Path, capsys) -> None:
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
    save_path.write_bytes(b"tampered")
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(checkpoint.to_json(), encoding="utf-8")
    out = tmp_path / "best.sts2movie"

    assert cli.main(["tas-search", "--checkpoint", str(checkpoint_path), "--budget", "0", "--out", str(out)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["checkpoint_valid"] is False
    assert report["acceptance_eligible"] is False
    assert not out.exists()


def test_tas_replay_live_uses_fake_observer_and_records_drift_evidence(tmp_path: Path, capsys, monkeypatch) -> None:
    movie_path = tmp_path / "run.sts2movie"
    movie = _victory_movie(movie_path)
    observed = []

    class Observer:
        def observe(self, frame, target_window, evidence_dir):
            observed.append((frame.frame, target_window.process, evidence_dir))
            return {
                "screen_hash": "actual-screen",
                "state_fingerprint": "actual-state",
                "screenshot_path": str(tmp_path / f"after-{frame.frame}.png"),
                "target_window": target_window.to_dict(),
            }

    class Controller:
        def send(self, action):
            observed.append(("input", action.input_plan()))

    class Detector:
        def detect(self, process: str):
            from sts2_tas.schema import TargetWindow, WindowBounds

            return TargetWindow(process=process, title="Main", bounds=WindowBounds(0, 0, 1920, 1080))

    monkeypatch.setattr("sts2_tas.tas_cli.NativeInputController", lambda: Controller())
    monkeypatch.setattr("sts2_tas.tas_cli.WindowDetector", lambda: Detector())
    monkeypatch.setattr("sts2_tas.tas_cli.DefaultLiveReplayObserver", lambda: Observer())

    assert cli.main(
        [
            "tas-replay",
            "--movie",
            str(movie_path),
            "--target-process",
            "SlayTheSpire2",
            "--verify",
            "--live",
            "--execute",
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ]
    ) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["acceptance_source"] == "live_windows_replay"
    assert report["tas_grade"] is False
    assert report["drift_count"] == len(movie.frames)
    assert report["drifts"][0]["expected_screen_hash"] == "screen-0"
    assert report["drifts"][0]["actual_screen_hash"] == "actual-screen"
    assert report["drifts"][0]["last_semantic_action"] == {"kind": "wait"}
    assert observed[0] == (0, "SlayTheSpire2", tmp_path / "evidence")
    assert observed[1][0] == "input"


def test_live_replay_default_observer_wait_click_and_unclassified_paths(tmp_path: Path) -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    target_window = TargetWindow(
        process="SlayTheSpire2",
        title="Main",
        bounds=WindowBounds(left=100, top=200, width=1280, height=720),
    )
    wait_frame = _frame(0)
    object.__setattr__(
        wait_frame,
        "physical_input",
        [
            PhysicalInput(index=0, kind="wait", frames=1),
            PhysicalInput(index=1, kind="click", x=150, y=250),
        ],
    )
    object.__setattr__(wait_frame, "decision_context", "")
    movie = TasMovie(run_id="run-live", frames=[wait_frame])
    sent = []

    class Controller:
        def send(self, action):
            sent.append(action.input_plan())

    report = replay_movie_live(
        movie,
        target_window=target_window,
        controller=Controller(),
        observer=DefaultLiveReplayObserver(),
        evidence_dir=tmp_path,
    )

    assert sent == [{"kind": "click", "x": 150, "y": 250}]
    assert report["drift_count"] == 0
    assert report["unclassified_screen_count"] == 1


def test_physical_click_adapter_rejects_missing_coordinates() -> None:
    from sts2_tas.schema import TargetWindow, WindowBounds

    target_window = TargetWindow(
        process="SlayTheSpire2",
        title="Main",
        bounds=WindowBounds(left=0, top=0, width=1280, height=720),
    )
    physical_input = PhysicalInput(index=0, kind="click", x=10, y=20)
    object.__setattr__(physical_input, "x", None)

    with pytest.raises(ValueError, match="coordinates"):
        automation_action_from_physical_input(physical_input, target_window=target_window)


def test_tas_verify_live_requires_five_clean_victories_for_tas_grade(tmp_path: Path, capsys, monkeypatch) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)

    class Observer:
        def observe(self, frame, target_window, evidence_dir):
            return {
                "screen_hash": frame.screen_hash,
                "state_fingerprint": frame.state_fingerprint,
                "screenshot_path": None,
                "target_window": target_window.to_dict(),
            }

    class Controller:
        def send(self, action):
            return None

    class Detector:
        def detect(self, process: str):
            from sts2_tas.schema import TargetWindow, WindowBounds

            return TargetWindow(process=process, title="Main", bounds=WindowBounds(0, 0, 1920, 1080))

    monkeypatch.setattr("sts2_tas.tas_cli.NativeInputController", lambda: Controller())
    monkeypatch.setattr("sts2_tas.tas_cli.WindowDetector", lambda: Detector())
    monkeypatch.setattr("sts2_tas.tas_cli.DefaultLiveReplayObserver", lambda: Observer())

    assert cli.main(["tas-verify", "--movie", str(movie_path), "--runs", "5", "--live", "--execute"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["acceptance_source"] == "live_windows_replay"
    assert report["victories"] == 5
    assert report["tas_grade"] is True


def test_tas_replay_live_without_execute_does_not_send_native_input(tmp_path: Path, capsys, monkeypatch) -> None:
    movie_path = tmp_path / "run.sts2movie"
    _victory_movie(movie_path)
    sent = []

    class Controller:
        def send(self, action):  # pragma: no cover
            sent.append(action)

    class Detector:
        def detect(self, process: str):
            from sts2_tas.schema import TargetWindow, WindowBounds

            return TargetWindow(process=process, title="Main", bounds=WindowBounds(0, 0, 1920, 1080))

    monkeypatch.setattr("sts2_tas.tas_cli.NativeInputController", lambda: Controller())
    monkeypatch.setattr("sts2_tas.tas_cli.WindowDetector", lambda: Detector())

    assert cli.main(["tas-replay", "--movie", str(movie_path), "--target-process", "SlayTheSpire2", "--live"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert sent == []
    assert report["execute"] is False
    assert report["drift_count"] == len(TasMovie.load(movie_path).frames)
    assert report["tas_grade"] is False


def test_tas_record_live_writes_observed_movie(tmp_path: Path, capsys, monkeypatch) -> None:
    movie_path = tmp_path / "recorded.sts2movie"

    class Observer:
        def observe(self, frame, target_window, evidence_dir):
            return {
                "screen_hash": "screen-live",
                "state_fingerprint": "state-live",
                "screenshot_path": None,
                "target_window": target_window.to_dict(),
            }

    class Detector:
        def detect(self, process: str):
            from sts2_tas.schema import TargetWindow, WindowBounds

            return TargetWindow(process=process, title="Main", bounds=WindowBounds(0, 0, 1920, 1080))

    monkeypatch.setattr("sts2_tas.tas_cli.WindowDetector", lambda: Detector())
    monkeypatch.setattr("sts2_tas.tas_cli.DefaultLiveReplayObserver", lambda: Observer())

    assert cli.main(
        [
            "tas-record",
            "--target-process",
            "SlayTheSpire2",
            "--movie",
            str(movie_path),
            "--run-id",
            "live-record",
            "--live",
            "--frames",
            "1",
        ]
    ) == 0

    report = json.loads(capsys.readouterr().out)
    movie = TasMovie.load(movie_path)
    assert report["frames"] == 1
    assert movie.frames[0].screen_hash == "screen-live"
    assert movie.frames[0].source_policy == "live_record"


def test_tas_search_rejects_negative_budget(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="budget"):
        cli.main(["tas-search", "--checkpoint", str(tmp_path / "checkpoint.json"), "--budget", "-1", "--out", str(tmp_path / "out.sts2movie")])


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
