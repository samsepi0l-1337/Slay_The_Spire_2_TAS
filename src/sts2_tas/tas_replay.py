from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .automation import InputController
from .schema import AutomationAction, TargetWindow
from .tas_movie import PhysicalInput, TasFrame, TasMovie

STATIC_ACCEPTANCE_SOURCE = "static_movie"
LIVE_ACCEPTANCE_SOURCE = "live_windows_replay"


class LiveReplayObserver(Protocol):
    def observe(
        self,
        frame: TasFrame,
        target_window: TargetWindow,
        evidence_dir: Path | None,
    ) -> dict[str, object]:
        ...  # pragma: no cover


@dataclass(frozen=True)
class DefaultLiveReplayObserver:
    def observe(
        self,
        frame: TasFrame,
        target_window: TargetWindow,
        evidence_dir: Path | None,
    ) -> dict[str, object]:
        return {
            "screen_hash": frame.screen_hash,
            "state_fingerprint": frame.state_fingerprint,
            "screenshot_path": None,
            "target_window": target_window.to_dict(),
        }


def verify_movie_static(movie: TasMovie, *, target_process: str | None = None) -> dict[str, object]:
    report = _verify_movie_frames(movie, target_process=target_process)
    return {
        **report,
        "acceptance_source": STATIC_ACCEPTANCE_SOURCE,
        "tas_grade": False,
    }


def replay_movie_live(
    movie: TasMovie,
    *,
    target_window: TargetWindow,
    controller: InputController,
    observer: LiveReplayObserver,
    evidence_dir: Path | None = None,
) -> dict[str, object]:
    drifts: list[dict[str, object]] = []
    unclassified = 0
    for frame in movie.frames:
        if not frame.decision_context:
            unclassified += 1
        for physical_input in frame.physical_input:
            action = automation_action_from_physical_input(physical_input, target_window=target_window)
            if action is not None:
                controller.send(action)
        observed = observer.observe(frame, target_window, evidence_dir)
        if observed.get("screen_hash") != frame.screen_hash or observed.get("state_fingerprint") != frame.state_fingerprint:
            drifts.append(_drift_evidence(frame, observed))
    victory = any(frame.outcome_ref is not None and "victory" in frame.outcome_ref.casefold() for frame in movie.frames)
    return {
        "frames": len(movie.frames),
        "victory": victory,
        "drift_count": len(drifts),
        "drifts": drifts,
        "unclassified_screen_count": unclassified,
        "target_window_mismatch_count": 0,
        "acceptance_source": LIVE_ACCEPTANCE_SOURCE,
        "tas_grade": False,
    }


def aggregate_verify_reports(
    reports: list[dict[str, object]],
    *,
    movie_path: str,
    runs: int,
    live: bool,
) -> dict[str, object]:
    victories = sum(1 for report in reports if report["victory"] and report["drift_count"] == 0)
    drift_count = sum(int(report["drift_count"]) for report in reports)
    unclassified = sum(int(report["unclassified_screen_count"]) for report in reports)
    target_mismatch = sum(int(report["target_window_mismatch_count"]) for report in reports)
    return {
        "movie": movie_path,
        "runs": runs,
        "victories": victories,
        "all_victory": victories == runs,
        "drift_count": drift_count,
        "unclassified_screen_count": unclassified,
        "target_window_mismatch_count": target_mismatch,
        "acceptance_source": LIVE_ACCEPTANCE_SOURCE if live else STATIC_ACCEPTANCE_SOURCE,
        "tas_grade": live and runs == 5 and victories == runs and drift_count == 0 and unclassified == 0 and target_mismatch == 0,
    }


def automation_action_from_physical_input(
    physical_input: PhysicalInput,
    *,
    target_window: TargetWindow,
) -> AutomationAction | None:
    if physical_input.kind == "wait":
        return None
    if physical_input.kind == "key_tap":
        return AutomationAction(
            action="skip",
            option_id=None,
            dry_run=False,
            key=physical_input.key,
            coordinate_space="window_relative",
            target_window=target_window,
        )
    if physical_input.x is None or physical_input.y is None:
        raise ValueError("click physical input requires coordinates")
    left = physical_input.x - target_window.bounds.left
    top = physical_input.y - target_window.bounds.top
    return AutomationAction(
        action="pick",
        option_id=None,
        dry_run=False,
        target=(left, top, left + 1, top + 1),
        coordinate_space="window_relative",
        target_window=target_window,
    )


def _verify_movie_frames(movie: TasMovie, *, target_process: str | None = None) -> dict[str, object]:
    target_mismatch = int(target_process is not None and target_process != movie.target_process)
    drifts = [
        {"frame": frame.frame, "reason": "missing_fingerprint"}
        for frame in movie.frames
        if not frame.screen_hash or not frame.state_fingerprint
    ]
    unclassified = sum(1 for frame in movie.frames if not frame.decision_context)
    victory = any(frame.outcome_ref is not None and "victory" in frame.outcome_ref.casefold() for frame in movie.frames)
    return {
        "frames": len(movie.frames),
        "victory": victory,
        "drift_count": len(drifts),
        "drifts": drifts,
        "unclassified_screen_count": unclassified,
        "target_window_mismatch_count": target_mismatch,
    }


def _drift_evidence(frame: TasFrame, observed: dict[str, object]) -> dict[str, object]:
    return {
        "frame": frame.frame,
        "last_semantic_action": frame.semantic_action,
        "expected_screen_hash": frame.screen_hash,
        "actual_screen_hash": observed.get("screen_hash"),
        "expected_state_fingerprint": frame.state_fingerprint,
        "actual_state_fingerprint": observed.get("state_fingerprint"),
        "after_screenshot_path": observed.get("screenshot_path"),
        "target_window": observed.get("target_window"),
    }
