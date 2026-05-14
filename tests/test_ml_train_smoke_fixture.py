"""Committed fixture used by Windows exe CI must load and train on CPU."""

from __future__ import annotations

from pathlib import Path

from sts2_tas.model import train_torch_model
from sts2_tas.torch_dataset import load_game_steps

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ml-train-smoke.jsonl"


def test_ml_train_smoke_fixture_loads_and_trains() -> None:
    steps = load_game_steps(FIXTURE)
    assert len(steps) >= 2
    model = train_torch_model(
        steps,
        "ironclad",
        epochs=1,
        batch_size=2,
        device="cpu",
        d_model=32,
        fusion_layers=1,
        ffn_dim=64,
    )
    assert model.character == "ironclad"
    assert model.catalog.size > 0
