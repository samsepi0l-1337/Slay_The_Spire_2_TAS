from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import torch

from sts2_tas.dataset import JsonlTransitionWriter
from sts2_tas.env import Sts2Env
from sts2_tas.executor import MacroExecutor
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot

ACTION_TYPES = (
    "play_card",
    "end_turn",
    "choose_reward",
    "choose_map_node",
    "choose_event_option",
    "shop_buy",
    "shop_remove",
)
FEATURE_DIM = 24
DEFAULT_GAMMA = 0.95
DEFAULT_ALPHA = 0.05
DEFAULT_SEARCH_DEPTH = 2
DEFAULT_MAX_STEPS = 32


def feature_vector(snapshot: TelemetrySnapshot, action: MacroAction) -> list[float]:
    player = snapshot.player
    enemies = snapshot.enemies
    card = _card(snapshot, action)
    damage = int(card.get("damage", 0))
    block = int(card.get("block", 0))
    cost = int(card.get("cost", 0))
    target_slot = action.args.get("target_slot")
    lethal = 0.0
    if isinstance(target_slot, int) and 0 <= target_slot < len(enemies):
        hp = int(enemies[target_slot].get("hp", 0))
        enemy_block = int(enemies[target_slot].get("block", 0))
        if hp > 0 and max(0, damage - enemy_block) >= hp:
            lethal = 1.0
    max_hp = max(int(player["max_hp"]), 1)
    return [
        float(player["hp"]) / max_hp,
        float(player["max_hp"]) / 200.0,
        float(player["energy"]) / 10.0,
        float(player["block"]) / 50.0,
        float(player["gold"]) / 999.0,
        float(snapshot.floor) / 50.0,
        float(snapshot.act) / 4.0,
        float(sum(int(enemy.get("hp", 0)) for enemy in enemies)) / 200.0,
        float(sum(int(enemy.get("block", 0)) for enemy in enemies)) / 50.0,
        float(len(snapshot.hand)) / 10.0,
        *[1.0 if action.action_type == action_type else 0.0 for action_type in ACTION_TYPES],
        float(action.args.get("hand_slot", 0)) / 10.0,
        float(action.args.get("target_slot", 0)) / 10.0,
        float(_choice_slot(action)) / 10.0,
        float(damage) / 50.0,
        float(block) / 50.0,
        float(cost) / 5.0,
        lethal,
    ]


class _QNetwork(torch.nn.Module):
    def __init__(self, input_size: int) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(input_size, 1)
        torch.nn.init.zeros_(self.linear.weight)
        torch.nn.init.zeros_(self.linear.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.linear(features)


class QStarPolicy:
    def __init__(self, gamma: float = DEFAULT_GAMMA, alpha: float = DEFAULT_ALPHA, updates: int = 0) -> None:
        self.gamma = gamma
        self.alpha = alpha
        self.updates = updates
        self.model = _QNetwork(FEATURE_DIM)
        self._optimizer = torch.optim.SGD(self.model.parameters(), lr=alpha)

    @classmethod
    def load(cls, path: Path) -> "QStarPolicy":
        artifact = _read_artifact(path)
        if artifact.get("algorithm") != "qstar":
            raise ValueError(f"unsupported algorithm: {artifact.get('algorithm')}")
        policy = cls(
            gamma=float(artifact.get("gamma", DEFAULT_GAMMA)),
            alpha=float(artifact.get("alpha", DEFAULT_ALPHA)),
            updates=int(artifact.get("updates", 0)),
        )
        state = {
            key: value if isinstance(value, torch.Tensor) else torch.tensor(value, dtype=torch.float32)
            for key, value in artifact["model_state"].items()
        }
        policy.model.load_state_dict(state)
        policy._optimizer = torch.optim.SGD(policy.model.parameters(), lr=policy.alpha)
        return policy

    @classmethod
    def load_or_create(cls, path: Path) -> "QStarPolicy":
        return cls.load(path) if path.exists() else cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "algorithm": "qstar",
            "gamma": self.gamma,
            "alpha": self.alpha,
            "updates": self.updates,
            "model_state": self.model.state_dict(),
        }
        if path.suffix == ".json":
            encoded = {**artifact, "model_state": {key: value.tolist() for key, value in artifact["model_state"].items()}}
            path.write_text(json.dumps(encoded, sort_keys=True))
            return
        torch.save(artifact, path)

    def q_value(self, snapshot: TelemetrySnapshot, action: MacroAction) -> float:
        with torch.no_grad():
            return float(self.model(_feature_tensor(snapshot, action)).item())

    def select(self, snapshot: TelemetrySnapshot, search_depth: int = DEFAULT_SEARCH_DEPTH) -> MacroAction:
        legal = snapshot.valid_actions
        if not legal:
            raise ValueError("no legal actions")
        return max(legal, key=lambda action: self.qstar(snapshot, action, search_depth))

    def update(
        self,
        snapshot: TelemetrySnapshot,
        action: MacroAction,
        reward: float,
        next_snapshot: TelemetrySnapshot,
        terminated: bool,
    ) -> float:
        predicted = self.model(_feature_tensor(snapshot, action)).squeeze()
        with torch.no_grad():
            target_value = reward
            if not terminated and next_snapshot.valid_actions:
                target_value += self.gamma * max(self.q_value(next_snapshot, nxt) for nxt in next_snapshot.valid_actions)
            target = torch.tensor(target_value, dtype=torch.float32)
        loss = torch.nn.functional.mse_loss(predicted, target)
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()
        self.updates += 1
        return float(loss.item())

    def qstar(self, snapshot: TelemetrySnapshot, action: MacroAction, depth: int) -> float:
        if depth <= 0:
            return self.q_value(snapshot, action)
        nxt, reward, terminated = simulate(snapshot, action)
        if terminated or not nxt.valid_actions:
            return reward
        future = max(self.qstar(nxt, nxt_action, depth - 1) for nxt_action in nxt.valid_actions)
        return reward + self.gamma * future


def simulate(snapshot: TelemetrySnapshot, action: MacroAction) -> tuple[TelemetrySnapshot, float, bool]:
    env = Sts2Env(snapshot)
    _, reward, terminated, _, _ = env.step(env.action_space.index_of(action))
    return env.snapshot, reward, terminated


def run_qstar(
    snapshot: TelemetrySnapshot,
    model: Path,
    output: Path,
    episodes: int = 1,
    search_depth: int = DEFAULT_SEARCH_DEPTH,
    max_steps: int = DEFAULT_MAX_STEPS,
    executor: MacroExecutor | None = None,
) -> dict[str, Any]:
    policy = QStarPolicy.load_or_create(model)
    writer = JsonlTransitionWriter(output)
    transitions = 0
    plans = 0
    for _ in range(episodes):
        env = Sts2Env(TelemetrySnapshot.from_dict(snapshot.to_dict()), writer=writer, policy_id="qstar")
        env.reset()
        for _ in range(max_steps):
            current = env.snapshot
            if not current.valid_actions:
                break
            action = policy.select(current, search_depth)
            if executor is not None:
                _emit(executor, action)
                plans += 1
            _, reward, terminated, _, _ = env.step(env.action_space.index_of(action))
            policy.update(current, action, reward, env.snapshot, terminated)
            transitions += 1
            if terminated:
                break
        policy.save(model)
    return {
        "algorithm": "qstar",
        "episodes": episodes,
        "transitions": transitions,
        "updates": policy.updates,
        "model": str(model),
        "output": str(output),
        "search_depth": search_depth,
        "plans": plans,
    }


def _emit(executor: MacroExecutor, action: MacroAction) -> None:
    if executor.execute_enabled:
        executor.execute(action)
        return
    executor.plan(action)


def _card(snapshot: TelemetrySnapshot, action: MacroAction) -> dict[str, Any]:
    if action.action_type != "play_card":
        return {}
    hand_slot = action.args.get("hand_slot", 0)
    if not isinstance(hand_slot, int) or hand_slot < 0 or hand_slot >= len(snapshot.hand):
        return {}
    return snapshot.hand[hand_slot]


def _choice_slot(action: MacroAction) -> int:
    for key in ("choice_slot", "node_slot", "item_slot", "card_slot"):
        if key in action.args:
            return int(action.args[key])
    return 0


def _feature_tensor(snapshot: TelemetrySnapshot, action: MacroAction) -> torch.Tensor:
    return torch.tensor(feature_vector(snapshot, action), dtype=torch.float32)


def _read_artifact(path: Path) -> dict[str, Any]:
    try:
        return torch.load(path, weights_only=False)
    except (OSError, RuntimeError, ValueError, pickle.UnpicklingError):
        return json.loads(path.read_text())
