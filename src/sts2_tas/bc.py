from __future__ import annotations

import json
import pickle
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from sts2_tas.telemetry_schema import MacroAction


def state_key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class BehavioralCloningPolicy:
    table: dict[str, dict[str, Any]]
    feature_schema: dict[str, Any]
    model_state: dict[str, torch.Tensor]

    @classmethod
    def load(cls, path: Path) -> "BehavioralCloningPolicy":
        try:
            artifact = torch.load(path, weights_only=False)
        except (OSError, RuntimeError, ValueError, pickle.UnpicklingError):
            artifact = json.loads(path.read_text())
        model_state = {
            key: value if isinstance(value, torch.Tensor) else torch.tensor(value, dtype=torch.float32)
            for key, value in artifact.get("model_state", {}).items()
        }
        return cls(
            artifact["table"],
            artifact.get("feature_schema", _legacy_feature_schema()),
            model_state,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "algorithm": "behavioral-cloning",
            "feature_schema": self.feature_schema,
            "model_state": self.model_state,
            "table": self.table,
        }
        if path.suffix == ".json":
            json_artifact = {**artifact, "model_state": {key: value.tolist() for key, value in self.model_state.items()}}
            path.write_text(json.dumps(json_artifact, sort_keys=True))
            return
        torch.save(artifact, path)

    def predict(self, state: dict[str, Any], valid_actions: list[MacroAction]) -> MacroAction:
        if self.model_state:
            return max(valid_actions, key=lambda action: self._score(state, action))
        encoded = self.table.get(state_key(state))
        if encoded is None:
            return valid_actions[0]
        action = MacroAction.from_dict(encoded)
        return action if action in valid_actions else valid_actions[0]

    def _score(self, state: dict[str, Any], action: MacroAction) -> float:
        model = _TorchScorer(len(_feature_vector(state, action, self.feature_schema)))
        model.load_state_dict(self.model_state)
        model.eval()
        with torch.no_grad():
            features = torch.tensor(_feature_vector(state, action, self.feature_schema), dtype=torch.float32)
            return float(model(features).item())


def train_behavioral_cloning(dataset: Path, model: Path) -> BehavioralCloningPolicy:
    samples = _read_jsonl(dataset)
    feature_schema = _build_feature_schema(samples)
    model_state = _train_torch_scorer(samples, feature_schema)
    votes: dict[str, Counter[str]] = {}
    encoded_actions: dict[str, dict[str, Any]] = {}
    for sample in samples:
        key = state_key(sample["state"])
        action = sample["chosen_action"]
        encoded = json.dumps(action, sort_keys=True)
        votes.setdefault(key, Counter())[encoded] += 1
        encoded_actions[encoded] = action
    table = {key: encoded_actions[counter.most_common(1)[0][0]] for key, counter in votes.items()}
    policy = BehavioralCloningPolicy(table, feature_schema, model_state)
    policy.save(model)
    return policy


def evaluate_behavioral_cloning(dataset: Path, model: Path) -> dict[str, float | int]:
    policy = BehavioralCloningPolicy.load(model)
    total = 0
    correct = 0
    for sample in _read_jsonl(dataset):
        valid = [MacroAction.from_dict(action) for action in sample["valid_actions"]]
        predicted = policy.predict(sample["state"], valid)
        correct += int(predicted == MacroAction.from_dict(sample["chosen_action"]))
        total += 1
    accuracy = correct / total if total else 0.0
    return {"samples": total, "correct": correct, "accuracy": accuracy}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class _TorchScorer(torch.nn.Module):
    def __init__(self, input_size: int) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(input_size, 1)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.linear(features)


def _legacy_feature_schema() -> dict[str, Any]:
    return {
        "state_numeric_keys": [],
        "state_categorical_values": {},
        "action_types": [],
        "action_arg_keys": [],
    }


def _build_feature_schema(samples: list[dict[str, Any]]) -> dict[str, Any]:
    state_numeric_keys: set[str] = set()
    state_categorical_values: dict[str, set[str]] = {}
    action_types: set[str] = set()
    action_arg_keys: set[str] = set()
    for sample in samples:
        for key, value in sample["state"].items():
            if isinstance(value, int | float):
                state_numeric_keys.add(key)
            elif isinstance(value, str):
                state_categorical_values.setdefault(key, set()).add(value)
        for action in sample["valid_actions"]:
            action_types.add(action["action_type"])
            for key, value in action.get("args", {}).items():
                if isinstance(value, int | float):
                    action_arg_keys.add(key)
    return {
        "state_numeric_keys": sorted(state_numeric_keys),
        "state_categorical_values": {key: sorted(values) for key, values in sorted(state_categorical_values.items())},
        "action_types": sorted(action_types),
        "action_arg_keys": sorted(action_arg_keys),
    }


def _feature_vector(state: dict[str, Any], action: MacroAction, schema: dict[str, Any]) -> list[float]:
    state_features = _state_features(state, schema)
    action_features = _action_features(action, schema)
    interactions = [state_value * action_value for state_value in state_features for action_value in action_features]
    return [*state_features, *action_features, *interactions]


def _state_features(state: dict[str, Any], schema: dict[str, Any]) -> list[float]:
    numeric = [float(state.get(key, 0.0)) for key in schema["state_numeric_keys"]]
    categorical = [
        1.0 if state.get(key) == value else 0.0
        for key, values in schema["state_categorical_values"].items()
        for value in values
    ]
    return [*numeric, *categorical]


def _action_features(action: MacroAction, schema: dict[str, Any]) -> list[float]:
    action_type = [1.0 if action.action_type == value else 0.0 for value in schema["action_types"]]
    args = [float(action.args.get(key, 0.0)) for key in schema["action_arg_keys"]]
    return [*action_type, *args]


def _train_torch_scorer(samples: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, torch.Tensor]:
    torch.manual_seed(0)
    input_size = len(_feature_vector(samples[0]["state"], MacroAction.from_dict(samples[0]["valid_actions"][0]), schema))
    model = _TorchScorer(input_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.05)
    for _ in range(300):
        for sample in samples:
            valid_actions = [MacroAction.from_dict(action) for action in sample["valid_actions"]]
            chosen = MacroAction.from_dict(sample["chosen_action"])
            features = torch.tensor(
                [_feature_vector(sample["state"], action, schema) for action in valid_actions],
                dtype=torch.float32,
            )
            logits = model(features).squeeze(-1).unsqueeze(0)
            target = torch.tensor([valid_actions.index(chosen)], dtype=torch.long)
            loss = torch.nn.functional.cross_entropy(logits, target)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model.state_dict()
