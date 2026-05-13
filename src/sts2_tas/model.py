from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import EntityCatalog
from .encoding import NUMERIC_FEATURE_DIM, TOKEN_TYPE_IDS, encode_game_step
from .ml_schema import GameStep
from .torch_dataset import GameStepTorchDataset, collate_encoded_steps
from .torch_model import EntityTransformerActorCritic, TorchModelConfig


@dataclass(frozen=True)
class TorchTrainedRecommender:
    character: str
    catalog: EntityCatalog
    model: EntityTransformerActorCritic


@dataclass(frozen=True)
class CandidateRecommendation:
    action_id: str
    action_type: str
    option_id: str | None
    score: float


@dataclass(frozen=True)
class Recommendation:
    best: CandidateRecommendation
    candidates: list[CandidateRecommendation]


def train_torch_model(
    steps: list[GameStep],
    character: str,
    *,
    epochs: int = 30,
    batch_size: int = 128,
    device: str = "auto",
    d_model: int = 256,
    heads: int = 4,
    fusion_layers: int = 4,
    ffn_dim: int = 1024,
    dropout: float = 0.1,
) -> TorchTrainedRecommender:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader

    character_steps = [step for step in steps if step.state.character == character and step.chosen_action_id is not None]
    dataset = GameStepTorchDataset(character_steps)
    runtime_device = _torch_device(device)
    model = EntityTransformerActorCritic(
        vocab_size=dataset.catalog.size,
        token_type_count=len(TOKEN_TYPE_IDS),
        numeric_dim=NUMERIC_FEATURE_DIM,
        d_model=d_model,
        heads=heads,
        fusion_layers=fusion_layers,
        ffn_dim=ffn_dim,
        dropout=dropout,
    ).to(runtime_device)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_encoded_steps)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    value_loss = nn.BCEWithLogitsLoss()
    for _ in range(max(epochs, 1)):
        model.train()
        for batch in loader:
            batch = {key: value.to(runtime_device) for key, value in batch.items()}
            output = model(
                token_ids=batch["token_ids"],
                token_types=batch["token_types"],
                numeric_features=batch["numeric_features"],
                attention_mask=batch["attention_mask"],
                action_positions=batch["action_positions"],
                action_mask=batch["action_mask"],
            )
            loss = nn.functional.cross_entropy(output.policy_logits, batch["labels"])
            outcome_mask = batch["outcome_mask"]
            if outcome_mask.any():
                loss = loss + 0.5 * value_loss(output.value[outcome_mask], batch["outcome_values"][outcome_mask])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    model.eval()
    return TorchTrainedRecommender(character=character, catalog=dataset.catalog, model=model.cpu())


def save_model(model: TorchTrainedRecommender, path: Path) -> None:
    if path.suffix != ".pt":
        raise ValueError("torch models must be saved to a .pt file")
    path.parent.mkdir(parents=True, exist_ok=True)
    _save_torch_model(model, path)


def load_model(path: Path) -> TorchTrainedRecommender:
    if path.suffix != ".pt":
        raise ValueError("torch model loading expects a .pt file")
    return _load_torch_model(path)


def recommend(model: TorchTrainedRecommender, step: GameStep) -> Recommendation:
    import torch

    if step.state.character != model.character:
        raise ValueError(f"step character {step.state.character!r} does not match model character {model.character!r}")
    encoded = encode_game_step(_step_with_query_label(step), model.catalog)
    batch = collate_encoded_steps([encoded])
    with torch.no_grad():
        output = model.model(
            token_ids=batch["token_ids"],
            token_types=batch["token_types"],
            numeric_features=batch["numeric_features"],
            attention_mask=batch["attention_mask"],
            action_positions=batch["action_positions"],
            action_mask=batch["action_mask"],
        )
        scores = torch.softmax(output.policy_logits, dim=1)[0].tolist()
    candidates = []
    for action, score in zip(step.actions, scores, strict=True):
        if not action.legal:
            continue
        candidates.append(
            CandidateRecommendation(
                action_id=action.identity,
                action_type=action.action_type,
                option_id=action.option_id,
                score=float(score),
            )
        )
    ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    return Recommendation(best=ranked[0], candidates=ranked)


def _step_with_query_label(step: GameStep) -> GameStep:
    label_action = next(action for action in step.actions if action.legal)
    return GameStep(
        state=step.state,
        actions=step.actions,
        chosen_action_id=label_action.identity,
        outcome=step.outcome,
        observation=step.observation,
        screenshot_path=step.screenshot_path,
    )


def _torch_device(device: str) -> str:
    import torch

    if device != "auto":
        return device
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _save_torch_model(model: TorchTrainedRecommender, path: Path) -> None:
    import torch

    torch.save(
        {
            "format": "sts2_tas_torch_recommender_v1",
            "character": model.character,
            "catalog": model.catalog.to_dict(),
            "config": model.model.config.to_dict(),
            "state_dict": model.model.state_dict(),
        },
        path,
    )


def _load_torch_model(path: Path) -> TorchTrainedRecommender:
    import torch

    checkpoint: dict[str, Any] = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("format") != "sts2_tas_torch_recommender_v1":
        raise ValueError("unsupported torch model format")
    catalog = EntityCatalog.from_dict(checkpoint["catalog"])
    config = TorchModelConfig.from_dict(checkpoint["config"])
    model = EntityTransformerActorCritic(**config.to_dict())
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return TorchTrainedRecommender(
        character=str(checkpoint["character"]),
        catalog=catalog,
        model=model,
    )
