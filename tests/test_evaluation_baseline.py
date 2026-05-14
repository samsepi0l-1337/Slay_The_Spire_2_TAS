import json
from pathlib import Path

from sts2_tas import cli
from sts2_tas.evaluation import write_evaluation


def _episodes(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_evaluate_seeds_can_compare_candidate_against_rule_baseline(tmp_path: Path) -> None:
    candidate = _episodes(
        tmp_path / "candidate.jsonl",
        [
            {"seed": 1, "steps": 2, "choices": [], "victory": True},
            {"seed": 2, "steps": 4, "choices": [], "victory": True},
        ],
    )
    baseline = _episodes(
        tmp_path / "baseline.jsonl",
        [
            {"seed": 1, "steps": 3, "choices": [], "victory": True},
            {"seed": 2, "steps": 5, "choices": [], "victory": False},
        ],
    )

    exit_code = cli.main(["evaluate-seeds", "--episodes", str(candidate), "--baseline", str(baseline), "--out", str(tmp_path / "out.json")])

    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["candidate"]["win_rate"] == 1.0
    assert report["baseline"]["win_rate"] == 0.5
    assert report["delta"]["win_rate"] == 0.5
    assert report["delta"]["average_steps"] == -1.0


def test_write_evaluation_keeps_legacy_summary_shape(tmp_path: Path) -> None:
    episodes = _episodes(tmp_path / "episodes.jsonl", [{"seed": 1, "steps": 3, "choices": [], "victory": True}])

    evaluation = write_evaluation(episodes, tmp_path / "summary.json")

    assert evaluation.victories == 1
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == {
        "average_steps": 3.0,
        "episodes": 1,
        "victories": 1,
        "win_rate": 1.0,
    }
