from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .tas_checkpoint import TasCheckpoint
from .tas_movie import TasMovie


def add_tas_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    probe = subparsers.add_parser("tas-probe")
    probe.add_argument("--target-process", required=True)
    probe.add_argument("--out", type=Path, required=True)
    probe.add_argument("--frames", type=int, default=3)
    probe.set_defaults(handler=_tas_probe)

    record = subparsers.add_parser("tas-record")
    record.add_argument("--target-process", required=True)
    record.add_argument("--movie", type=Path, required=True)
    record.add_argument("--run-id", default="manual-record")
    record.add_argument("--game-version", default="unknown")
    record.add_argument("--branch", default="unknown")
    record.set_defaults(handler=_tas_record)

    replay = subparsers.add_parser("tas-replay")
    replay.add_argument("--movie", type=Path, required=True)
    replay.add_argument("--target-process", required=True)
    replay.add_argument("--verify", action="store_true")
    replay.set_defaults(handler=_tas_replay)

    verify = subparsers.add_parser("tas-verify")
    verify.add_argument("--movie", type=Path, required=True)
    verify.add_argument("--runs", type=int, required=True)
    verify.set_defaults(handler=_tas_verify)

    search = subparsers.add_parser("tas-search")
    search.add_argument("--checkpoint", type=Path, required=True)
    search.add_argument("--budget", type=int, required=True)
    search.add_argument("--out", type=Path, required=True)
    search.set_defaults(handler=_tas_search)


def _tas_probe(args: argparse.Namespace) -> None:
    if args.frames <= 0:
        raise ValueError("--frames must be positive")
    rows = [
        {
            "target_process": args.target_process,
            "frame": frame,
            "frame_counter": frame,
            "hook_attached": False,
            "mode": "python_fallback",
            "tas_grade": False,
            "passive_only": True,
            "window": None,
            "screen_hash": _stable_hash(f"{args.target_process}:{frame}:python_fallback"),
        }
        for frame in range(args.frames)
    ]
    _write_jsonl(args.out, rows)


def _tas_record(args: argparse.Namespace) -> None:
    movie = TasMovie(
        run_id=args.run_id,
        game_version=args.game_version,
        branch=args.branch,
        target_process=args.target_process,
        frames=[],
    )
    movie.write(args.movie)
    print(json.dumps({"movie": str(args.movie), "frames": 0, "target_process": args.target_process}, sort_keys=True))


def _tas_replay(args: argparse.Namespace) -> None:
    movie = TasMovie.load(args.movie)
    report = verify_movie(movie, target_process=args.target_process)
    print(json.dumps({"movie": str(args.movie), "verify": bool(args.verify), **report}, sort_keys=True))


def _tas_verify(args: argparse.Namespace) -> None:
    if args.runs <= 0:
        raise ValueError("--runs must be positive")
    movie = TasMovie.load(args.movie)
    reports = [verify_movie(movie, target_process=movie.target_process) for _ in range(args.runs)]
    victories = sum(1 for report in reports if report["victory"] and report["drift_count"] == 0)
    print(
        json.dumps(
            {
                "movie": str(args.movie),
                "runs": args.runs,
                "victories": victories,
                "all_victory": victories == args.runs,
                "drift_count": sum(int(report["drift_count"]) for report in reports),
                "unclassified_screen_count": sum(int(report["unclassified_screen_count"]) for report in reports),
                "target_window_mismatch_count": sum(int(report["target_window_mismatch_count"]) for report in reports),
            },
            sort_keys=True,
        )
    )


def _tas_search(args: argparse.Namespace) -> None:
    if args.budget < 0:
        raise ValueError("--budget must be non-negative")
    checkpoint = TasCheckpoint.from_json(args.checkpoint.read_text(encoding="utf-8"))
    checkpoint_valid = (
        checkpoint.validate_save()
        and checkpoint.validate_movie_prefix_hash()
        and checkpoint.validate_screen_state_fingerprints()
    )
    prefix = TasMovie(
        run_id=checkpoint.movie.run_id,
        game_version=checkpoint.movie.game_version,
        branch=checkpoint.movie.branch,
        target_process=checkpoint.movie.target_process,
        frames=checkpoint.movie.frames[: checkpoint.movie_prefix_length],
    )
    prefix.write(args.out)
    print(
        json.dumps(
            {
                "checkpoint": str(args.checkpoint),
                "checkpoint_valid": checkpoint_valid,
                "budget": args.budget,
                "out": str(args.out),
                "prefix_frames": len(prefix.frames),
            },
            sort_keys=True,
        )
    )


def verify_movie(movie: TasMovie, *, target_process: str | None = None) -> dict[str, object]:
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


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
