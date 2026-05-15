from __future__ import annotations

import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .recognition import OcrProvider, parse_ocr_screen
from .schema import RunEpisode

ScreenGrabber = Callable[..., Any]
ScoreBranch = Callable[[int, tuple[str, ...]], float]


@dataclass(frozen=True)
class BranchScoreWeights:
    victory: float = 1000.0
    floor: float = 10.0
    hp: float = 0.1
    step: float = -0.25


@dataclass(frozen=True)
class BranchSearchResult:
    seed: int
    choices: list[str]
    score: float
    pruned: int

    def to_dict(self) -> dict[str, int | float | list[str]]:
        return {
            "seed": self.seed,
            "choices": list(self.choices),
            "score": self.score,
            "pruned": self.pruned,
        }


def capture_screen(screenshot_out: Path, *, grabber: ScreenGrabber | None = None, bbox: tuple[int, int, int, int] | None = None) -> Path:
    try:
        capture = grabber or _pillow_screen_grabber
        image = capture(bbox=bbox) if bbox is not None else capture()
        screenshot_out.parent.mkdir(parents=True, exist_ok=True)
        image.save(screenshot_out)
    except Exception as error:
        raise RuntimeError(
            "live screen capture failed; on macOS check screen recording permission; "
            "on Windows remote SSH/non-interactive sessions use the interactive "
            "scheduled-task wrapper or use --capture-fixture"
        ) from error
    return screenshot_out


def _pillow_screen_grabber(*, bbox: tuple[int, int, int, int] | None = None) -> Any:
    from PIL import ImageGrab

    if bbox is None:
        return ImageGrab.grab()
    return ImageGrab.grab(bbox=bbox)


def backup_save(save_path: Path, backup_dir: Path) -> Path:
    if not save_path.is_file():
        raise ValueError(f"save file does not exist: {save_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(save_path, backup_dir)
    shutil.copy2(save_path, backup_path)
    return backup_path


def restore_save(save_path: Path, backup_dir: Path) -> Path:
    backup_path = _backup_path(save_path, backup_dir)
    if not backup_path.is_file():
        raise ValueError(f"backup file does not exist: {backup_path}")
    if save_path.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(save_path, backup_dir / f"{backup_path.name}.pre-restore")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, save_path)
    return save_path


def branch_and_bound_seed(
    *,
    seed: int,
    choices: list[str],
    max_depth: int,
    score_branch: ScoreBranch,
    bound_branch: ScoreBranch | None = None,
) -> BranchSearchResult:
    best_choices: list[str] = []
    best_score = float("-inf")
    pruned = 0

    def visit(path: tuple[str, ...]) -> None:
        nonlocal best_choices, best_score, pruned
        if path:
            score = score_branch(seed, path)
            if score > best_score:
                best_choices = list(path)
                best_score = score
        if len(path) >= max_depth:
            return
        for choice in choices:
            candidate = (*path, choice)
            if bound_branch is not None and bound_branch(seed, candidate) < best_score:
                pruned += 1
                continue
            visit(candidate)

    visit(())
    return BranchSearchResult(
        seed=seed,
        choices=best_choices,
        score=0.0 if best_score == float("-inf") else best_score,
        pruned=pruned,
    )


def score_branch_outcome(
    *,
    victory: bool,
    floor_reached: int,
    hp_remaining: int,
    steps: int,
    weights: BranchScoreWeights = BranchScoreWeights(),
) -> float:
    return (
        (weights.victory if victory else 0.0)
        + floor_reached * weights.floor
        + hp_remaining * weights.hp
        + steps * weights.step
    )


def mcts_seed_search(
    *,
    seed: int,
    choices: list[str],
    max_depth: int,
    iterations: int,
    score_branch: ScoreBranch,
    exploration: float = 1.4,
) -> BranchSearchResult:
    stats: dict[tuple[str, ...], tuple[int, float]] = {}
    best_choices: tuple[str, ...] = ()
    best_score = float("-inf")
    for _ in range(iterations):
        path: tuple[str, ...] = ()
        for _depth in range(max_depth):
            choice = _mcts_choice(path, choices, stats, exploration)
            path = (*path, choice)
            score = score_branch(seed, path)
            visits, total = stats.get(path, (0, 0.0))
            stats[path] = (visits + 1, total + score)
            if score > best_score:
                best_choices = path
                best_score = score
    return BranchSearchResult(
        seed=seed,
        choices=list(best_choices),
        score=0.0 if best_score == float("-inf") else best_score,
        pruned=0,
    )


def _mcts_choice(
    path: tuple[str, ...],
    choices: list[str],
    stats: dict[tuple[str, ...], tuple[int, float]],
    exploration: float,
) -> str:
    for choice in choices:
        if (*path, choice) not in stats:
            return choice
    total_visits = sum(stats[(*path, choice)][0] for choice in choices)
    return max(choices, key=lambda choice: _uct_score(stats[(*path, choice)], total_visits, exploration))


def _uct_score(stat: tuple[int, float], total_visits: int, exploration: float) -> float:
    visits, total = stat
    return (total / visits) + exploration * math.sqrt(math.log(total_visits) / visits)


def search_save_state_branches(
    *,
    seed: int,
    choices: list[str],
    save: Path,
    backup_dir: Path,
    max_depth: int,
    score_branch: ScoreBranch,
    bound_branch: ScoreBranch | None = None,
) -> BranchSearchResult:
    backup_save(save, backup_dir)

    def restored_score(candidate_seed: int, path: tuple[str, ...]) -> float:
        restore_save(save, backup_dir)
        return score_branch(candidate_seed, path)

    restored_bound: ScoreBranch | None = None
    if bound_branch is not None:

        def restored_bound(candidate_seed: int, path: tuple[str, ...]) -> float:
            restore_save(save, backup_dir)
            return bound_branch(candidate_seed, path)

    try:
        return branch_and_bound_seed(
            seed=seed,
            choices=choices,
            max_depth=max_depth,
            score_branch=restored_score,
            bound_branch=restored_bound,
        )
    finally:
        restore_save(save, backup_dir)


def _backup_path(save_path: Path, backup_dir: Path) -> Path:
    digest = hashlib.sha256(str(save_path.expanduser().absolute()).encode("utf-8")).hexdigest()[:12]
    return backup_dir / f"{save_path.stem}.{digest}{save_path.suffix}"


def run_seed_loop(
    *,
    seeds: list[int],
    screenshot: Path,
    ocr_provider: OcrProvider,
    episodes_out: Path,
    max_steps: int,
    victory_seeds: set[int] | None = None,
) -> list[RunEpisode]:
    victories = victory_seeds or set()
    episodes = [_run_seed(seed, screenshot, ocr_provider, max_steps, seed in victories) for seed in seeds]
    episodes_out.parent.mkdir(parents=True, exist_ok=True)
    with episodes_out.open("w", encoding="utf-8") as file:
        for episode in episodes:
            file.write(json.dumps(episode.to_dict(), sort_keys=True) + "\n")
    return episodes


def _run_seed(seed: int, screenshot: Path, ocr_provider: OcrProvider, max_steps: int, victory: bool) -> RunEpisode:
    parsed = parse_ocr_screen(screenshot, ocr_provider)
    choice = next(option for option in parsed.options if option.kind != "skip")
    choices = [{"action": "pick", "option_id": choice.id}][:max_steps]
    return RunEpisode(
        seed=seed,
        steps=len(choices),
        choices=choices,
        victory=victory,
    )
