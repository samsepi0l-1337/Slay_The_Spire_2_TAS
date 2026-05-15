from __future__ import annotations

import json
from pathlib import Path

from sts2_tas.bc import train_behavioral_cloning


def train_maskable_ppo_smoke(dataset: Path, model: Path, timesteps: int) -> dict[str, int | str]:
    policy = train_behavioral_cloning(dataset, model)
    payload = json.loads(model.read_text())
    payload["algorithm"] = "maskable-ppo-smoke"
    payload["timesteps"] = timesteps
    payload["policy_states"] = len(policy.table)
    model.write_text(json.dumps(payload, sort_keys=True))
    return {"algorithm": "maskable-ppo-smoke", "timesteps": timesteps, "policy_states": len(policy.table)}
