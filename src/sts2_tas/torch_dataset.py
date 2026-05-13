from __future__ import annotations

from pathlib import Path
from typing import Iterable

import torch
from torch.utils.data import Dataset

from .catalog import EntityCatalog
from .encoding import EncodedGameStep, encode_game_step
from .ml_schema import GameStep


class GameStepTorchDataset(Dataset[EncodedGameStep]):
    def __init__(self, steps: list[GameStep], catalog: EntityCatalog | None = None) -> None:
        self.steps = [step for step in steps if step.chosen_action_id is not None]
        if not self.steps:
            raise ValueError("torch training requires at least one labeled game step")
        self.catalog = catalog or EntityCatalog.from_steps(self.steps, version=self.steps[0].state.catalog_version)

    def __len__(self) -> int:
        return len(self.steps)

    def __getitem__(self, index: int) -> EncodedGameStep:
        return encode_game_step(self.steps[index], self.catalog)


def load_game_steps(path: Path) -> list[GameStep]:
    return [GameStep.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_game_steps(path: Path, steps: Iterable[GameStep]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for step in steps:
            file.write(step.to_json() + "\n")


def collate_encoded_steps(encoded_steps: list[EncodedGameStep]) -> dict[str, torch.Tensor]:
    max_tokens = max(len(step.token_ids) for step in encoded_steps)
    max_actions = max(len(step.action_positions) for step in encoded_steps)
    numeric_dim = len(encoded_steps[0].numeric_features[0])
    return {
        "token_ids": torch.tensor([_pad(step.token_ids, max_tokens, 0) for step in encoded_steps], dtype=torch.long),
        "token_types": torch.tensor([_pad(step.token_types, max_tokens, 0) for step in encoded_steps], dtype=torch.long),
        "numeric_features": torch.tensor(
            [_pad_rows(step.numeric_features, max_tokens, numeric_dim) for step in encoded_steps],
            dtype=torch.float32,
        ),
        "attention_mask": torch.tensor(
            [_pad(step.attention_mask, max_tokens, False) for step in encoded_steps],
            dtype=torch.bool,
        ),
        "action_positions": torch.tensor(
            [_pad(step.action_positions, max_actions, 0) for step in encoded_steps],
            dtype=torch.long,
        ),
        "action_mask": torch.tensor(
            [_pad(step.action_mask, max_actions, False) for step in encoded_steps],
            dtype=torch.bool,
        ),
        "labels": torch.tensor([step.label_action_index for step in encoded_steps], dtype=torch.long),
        "outcome_values": torch.tensor([step.outcome_value for step in encoded_steps], dtype=torch.float32),
    }


def _pad[T](values: list[T], size: int, fill: T) -> list[T]:
    return [*values, *([fill] * (size - len(values)))]


def _pad_rows(rows: list[list[float]], size: int, width: int) -> list[list[float]]:
    padding = [[0.0] * width for _ in range(size - len(rows))]
    return [*rows, *padding]
