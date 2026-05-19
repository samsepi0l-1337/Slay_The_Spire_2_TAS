from __future__ import annotations

import json
from pathlib import Path

import torch

from sts2_tas.bc import train_behavioral_cloning


def train_maskable_ppo_smoke(dataset: Path, model: Path, timesteps: int) -> dict[str, int | str]:
    policy = train_behavioral_cloning(dataset, model)
    if model.suffix == ".json":
        payload = json.loads(model.read_text())
    else:
        payload = torch.load(model, weights_only=False)
    payload["algorithm"] = "maskable-ppo-smoke"
    payload["timesteps"] = timesteps
    payload["policy_states"] = len(policy.table)
    if model.suffix == ".json":
        model.write_text(json.dumps(payload, sort_keys=True))
    else:
        torch.save(payload, model)
    return {"algorithm": "maskable-ppo-smoke", "timesteps": timesteps, "policy_states": len(policy.table)}
