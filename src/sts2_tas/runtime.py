from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .recognition import OcrProvider, parse_ocr_screen
from .schema import RunEpisode

ScreenGrabber = Callable[..., Any]
ScoreBranch = Callable[[int, tuple[str, ...]], float]


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
            "live screen capture failed; check OS screen recording permission or use --capture-fixture"
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

    try:
        return branch_and_bound_seed(
            seed=seed,
            choices=choices,
            max_depth=max_depth,
            score_branch=restored_score,
            bound_branch=bound_branch,
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
