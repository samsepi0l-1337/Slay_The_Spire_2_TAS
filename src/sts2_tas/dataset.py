from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .schema import DecisionSnapshot

FeatureRow = dict[str, int | str]
LabeledRow = tuple[FeatureRow, int]


def append_snapshot(path: Path, snapshot: DecisionSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(snapshot.to_json() + "\n")


def write_snapshots(path: Path, snapshots: Iterable[DecisionSnapshot]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for snapshot in snapshots:
            file.write(snapshot.to_json() + "\n")


def load_snapshots(path: Path) -> list[DecisionSnapshot]:
    return [
        DecisionSnapshot.from_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def candidate_rows(snapshots: Iterable[DecisionSnapshot]) -> list[LabeledRow]:
    rows: list[LabeledRow] = []
    for snapshot in snapshots:
        if snapshot.chosen is None:
            continue
        for option in snapshot.options:
            features: FeatureRow = {
                "game_version": snapshot.game_version,
                "branch": snapshot.branch,
                "character": snapshot.character,
                "ascension": snapshot.ascension,
                "floor": snapshot.floor,
                "hp": snapshot.hp,
                "gold": snapshot.gold,
                "deck_size": len(snapshot.deck),
                "relic_count": len(snapshot.relics),
                "option_id": option.id,
                "option_kind": option.kind,
            }
            for tag in option.tags:
                features[f"tag:{tag}"] = 1
            for relic in snapshot.relics:
                features[f"relic:{relic}"] = 1
            rows.append((features, int(snapshot.chosen.matches(option))))
    return rows
