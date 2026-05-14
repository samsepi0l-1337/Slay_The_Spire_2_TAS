from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import SeedEvaluation


def evaluate_episodes(path: Path) -> SeedEvaluation:
    rows = _load_episode_rows(path)
    count = len(rows)
    victories = sum(1 for row in rows if row.get("victory") is True)
    steps = sum(int(row["steps"]) for row in rows)
    return SeedEvaluation(
        episodes=count,
        victories=victories,
        win_rate=victories / count if count else 0.0,
        average_steps=steps / count if count else 0.0,
    )


def write_evaluation(episodes: Path, out: Path) -> SeedEvaluation:
    evaluation = evaluate_episodes(episodes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evaluation.to_dict(), sort_keys=True), encoding="utf-8")
    return evaluation


def compare_to_baseline(candidate_path: Path, baseline_path: Path) -> dict[str, Any]:
    candidate = evaluate_episodes(candidate_path)
    baseline = evaluate_episodes(baseline_path)
    return {
        "candidate": candidate.to_dict(),
        "baseline": baseline.to_dict(),
        "delta": {
            "win_rate": candidate.win_rate - baseline.win_rate,
            "average_steps": candidate.average_steps - baseline.average_steps,
            "victories": candidate.victories - baseline.victories,
        },
    }


def write_evaluation_report(episodes: Path, out: Path, *, baseline: Path | None = None) -> dict[str, Any]:
    report = evaluate_episodes(episodes).to_dict() if baseline is None else compare_to_baseline(episodes, baseline)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    return report


def _load_episode_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
