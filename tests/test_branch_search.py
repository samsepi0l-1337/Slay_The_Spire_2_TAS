from pathlib import Path

from sts2_tas.runtime import branch_and_bound_seed, search_save_state_branches


def test_branch_and_bound_seed_prunes_branches_below_best_bound() -> None:
    result = branch_and_bound_seed(
        seed=7,
        choices=["a", "b"],
        max_depth=1,
        score_branch=lambda _seed, path: 1.0 if path == ("a",) else 0.0,
        bound_branch=lambda _seed, path: -1.0 if path == ("b",) else 1.0,
    )

    assert result.seed == 7
    assert result.choices == ["a"]
    assert result.score == 1.0
    assert result.pruned == 1
    assert result.to_dict() == {"seed": 7, "choices": ["a"], "score": 1.0, "pruned": 1}


def test_search_save_state_branches_restores_save_before_each_candidate(tmp_path: Path) -> None:
    save = tmp_path / "save.dat"
    save.write_text("original", encoding="utf-8")
    observed = []

    def score_branch(_seed: int, path: tuple[str, ...]) -> float:
        observed.append(save.read_text(encoding="utf-8"))
        save.write_text("mutated", encoding="utf-8")
        return float(len(path))

    result = search_save_state_branches(
        seed=11,
        choices=["left"],
        save=save,
        backup_dir=tmp_path / "backups",
        max_depth=2,
        score_branch=score_branch,
    )

    assert result.choices == ["left", "left"]
    assert observed == ["original", "original"]
    assert save.read_text(encoding="utf-8") == "original"
