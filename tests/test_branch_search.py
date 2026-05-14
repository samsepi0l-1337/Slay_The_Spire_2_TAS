from pathlib import Path

from sts2_tas.runtime import BranchScoreWeights, branch_and_bound_seed, mcts_seed_search, score_branch_outcome, search_save_state_branches


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


def test_search_save_state_branches_restores_save_before_bound_checks(tmp_path: Path) -> None:
    save = tmp_path / "save.dat"
    save.write_text("original", encoding="utf-8")
    observed_bounds = []
    observed_scores = []

    def bound_branch(_seed: int, path: tuple[str, ...]) -> float:
        observed_bounds.append((path, save.read_text(encoding="utf-8")))
        save.write_text("bound-mutated", encoding="utf-8")
        return 1.0

    def score_branch(_seed: int, path: tuple[str, ...]) -> float:
        observed_scores.append((path, save.read_text(encoding="utf-8")))
        save.write_text("score-mutated", encoding="utf-8")
        return float(len(path))

    result = search_save_state_branches(
        seed=11,
        choices=["left", "right"],
        save=save,
        backup_dir=tmp_path / "backups",
        max_depth=1,
        score_branch=score_branch,
        bound_branch=bound_branch,
    )

    assert result.choices == ["left"]
    assert observed_bounds == [(("left",), "original"), (("right",), "original")]
    assert observed_scores == [(("left",), "original"), (("right",), "original")]
    assert save.read_text(encoding="utf-8") == "original"


def test_score_branch_outcome_weights_terminal_progress_and_cost() -> None:
    score = score_branch_outcome(
        victory=True,
        floor_reached=12,
        hp_remaining=37,
        steps=8,
        weights=BranchScoreWeights(victory=1000.0, floor=25.0, hp=0.5, step=-1.0),
    )

    assert score == 1310.5


def test_mcts_seed_search_prefers_high_value_branch_with_repeated_rollouts() -> None:
    scores = {
        ("left",): 1.0,
        ("right",): 5.0,
        ("left", "left"): 2.0,
        ("left", "right"): 4.0,
        ("right", "left"): 7.0,
        ("right", "right"): 6.0,
    }

    result = mcts_seed_search(
        seed=23,
        choices=["left", "right"],
        max_depth=2,
        iterations=24,
        score_branch=lambda _seed, path: scores[path],
        exploration=0.25,
    )

    assert result.seed == 23
    assert result.choices == ["right", "left"]
    assert result.score == 7.0
    assert result.pruned == 0
