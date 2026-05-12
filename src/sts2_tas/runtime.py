from __future__ import annotations

import json
import shutil
from pathlib import Path

from .recognition import OcrProvider, parse_ocr_screen
from .schema import RunEpisode


def backup_save(save_path: Path, backup_dir: Path) -> Path:
    if not save_path.is_file():
        raise ValueError(f"save file does not exist: {save_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / save_path.name
    shutil.copy2(save_path, backup_path)
    return backup_path


def restore_save(save_path: Path, backup_dir: Path) -> Path:
    backup_path = backup_dir / save_path.name
    if not backup_path.is_file():
        raise ValueError(f"backup file does not exist: {backup_path}")
    if save_path.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(save_path, backup_dir / f"{save_path.name}.pre-restore")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, save_path)
    return save_path


def run_seed_loop(
    *,
    seeds: list[int],
    screenshot: Path,
    ocr_provider: OcrProvider,
    episodes_out: Path,
    max_steps: int,
) -> list[RunEpisode]:
    episodes = [_run_seed(seed, screenshot, ocr_provider, max_steps) for seed in seeds]
    episodes_out.parent.mkdir(parents=True, exist_ok=True)
    with episodes_out.open("w", encoding="utf-8") as file:
        for episode in episodes:
            file.write(json.dumps(episode.to_dict(), sort_keys=True) + "\n")
    return episodes


def _run_seed(seed: int, screenshot: Path, ocr_provider: OcrProvider, max_steps: int) -> RunEpisode:
    parsed = parse_ocr_screen(screenshot, ocr_provider)
    choice = next(option for option in parsed.options if option.kind != "skip")
    return RunEpisode(
        seed=seed,
        steps=max_steps,
        choices=[{"action": "pick", "option_id": choice.id}],
    )
