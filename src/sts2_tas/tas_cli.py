from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .automation import NativeInputController
from .tas_checkpoint import TasCheckpoint
from .tas_movie import PhysicalInput, TasFrame, TasMovie
from .tas_replay import DefaultLiveReplayObserver, aggregate_verify_reports, replay_movie_live, verify_movie_static
from .windowing import WindowDetector


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
    record.add_argument("--live", action="store_true")
    record.add_argument("--frames", type=int, default=1)
    record.add_argument("--evidence-dir", type=Path)
    record.set_defaults(handler=_tas_record)

    replay = subparsers.add_parser("tas-replay")
    replay.add_argument("--movie", type=Path, required=True)
    replay.add_argument("--target-process", required=True)
    replay.add_argument("--verify", action="store_true")
    replay.add_argument("--live", action="store_true")
    replay.add_argument("--execute", action="store_true")
    replay.add_argument("--evidence-dir", type=Path)
    replay.set_defaults(handler=_tas_replay)

    verify = subparsers.add_parser("tas-verify")
    verify.add_argument("--movie", type=Path, required=True)
    verify.add_argument("--runs", type=int, required=True)
    verify.add_argument("--live", action="store_true")
    verify.add_argument("--execute", action="store_true")
    verify.add_argument("--evidence-dir", type=Path)
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
    if args.live:
        if args.frames <= 0:
            raise ValueError("--frames must be positive")
        target_window = WindowDetector().detect(args.target_process)
        observer = DefaultLiveReplayObserver()
        frames = []
        for frame_index in range(args.frames):
            placeholder = TasFrame(
                frame=frame_index,
                semantic_action={"kind": "live_observation"},
                physical_input=[],
                screen_hash="pending",
                state_fingerprint="pending",
                decision_context="live_observation",
                source_policy="live_record",
                label_source="live_record",
            )
            observed = observer.observe(placeholder, target_window, args.evidence_dir)
            frames.append(
                TasFrame(
                    frame=frame_index,
                    semantic_action={"kind": "live_observation"},
                    physical_input=[],
                    screen_hash=str(observed["screen_hash"]),
                    state_fingerprint=str(observed["state_fingerprint"]),
                    decision_context="live_observation",
                    source_policy="live_record",
                    label_source="live_record",
                )
            )
        movie = TasMovie(
            run_id=args.run_id,
            game_version=args.game_version,
            branch=args.branch,
            target_process=args.target_process,
            frames=frames,
        )
        movie.write(args.movie)
        print(json.dumps({"movie": str(args.movie), "frames": len(frames), "target_process": args.target_process}, sort_keys=True))
        return
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
    if args.live:
        target_window = WindowDetector().detect(args.target_process)
        report = replay_movie_live(
            movie,
            target_window=target_window,
            controller=NativeInputController(),
            observer=DefaultLiveReplayObserver(),
            evidence_dir=args.evidence_dir,
        )
    else:
        report = verify_movie(movie, target_process=args.target_process)
    print(json.dumps({"movie": str(args.movie), "verify": bool(args.verify), **report}, sort_keys=True))


def _tas_verify(args: argparse.Namespace) -> None:
    if args.runs <= 0:
        raise ValueError("--runs must be positive")
    movie = TasMovie.load(args.movie)
    if args.live:
        target_window = WindowDetector().detect(movie.target_process)
        reports = [
            replay_movie_live(
                movie,
                target_window=target_window,
                controller=NativeInputController(),
                observer=DefaultLiveReplayObserver(),
                evidence_dir=args.evidence_dir,
            )
            for _ in range(args.runs)
        ]
    else:
        reports = [verify_movie(movie, target_process=movie.target_process) for _ in range(args.runs)]
    print(json.dumps(aggregate_verify_reports(reports, movie_path=str(args.movie), runs=args.runs, live=args.live), sort_keys=True))


def _tas_search(args: argparse.Namespace) -> None:
    if args.budget < 0:
        raise ValueError("--budget must be non-negative")
    checkpoint = TasCheckpoint.from_json(args.checkpoint.read_text(encoding="utf-8"))
    checkpoint_valid = (
        checkpoint.validate_save()
        and checkpoint.validate_movie_prefix_hash()
        and checkpoint.validate_screen_state_fingerprints()
    )
    if not checkpoint_valid:
        print(
            json.dumps(
                {
                    "checkpoint": str(args.checkpoint),
                    "checkpoint_valid": False,
                    "acceptance_eligible": False,
                    "budget": args.budget,
                    "out": str(args.out),
                    "prefix_frames": 0,
                },
                sort_keys=True,
            )
        )
        return
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
                "acceptance_eligible": True,
                "budget": args.budget,
                "out": str(args.out),
                "prefix_frames": len(prefix.frames),
            },
            sort_keys=True,
        )
    )


def verify_movie(movie: TasMovie, *, target_process: str | None = None) -> dict[str, object]:
    return verify_movie_static(movie, target_process=target_process)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
