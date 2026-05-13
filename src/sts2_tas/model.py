from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from .catalog import EntityCatalog
from .dataset import FeatureRow, candidate_rows
from .encoding import NUMERIC_FEATURE_DIM, TOKEN_TYPE_IDS, encode_game_step
from .ml_schema import GameStep
from .schema import ChoiceOption, DecisionSnapshot
from .torch_dataset import GameStepTorchDataset, collate_encoded_steps
from .torch_model import EntityTransformerActorCritic, TorchModelConfig


@dataclass(frozen=True)
class TrainedRecommender:
    character: str
    pipeline: Pipeline


@dataclass(frozen=True)
class TorchTrainedRecommender:
    character: str
    catalog: EntityCatalog
    model: EntityTransformerActorCritic


@dataclass(frozen=True)
class CandidateRecommendation:
    option_id: str
    action: str
    score: float


@dataclass(frozen=True)
class Recommendation:
    best: CandidateRecommendation
    candidates: list[CandidateRecommendation]


def train_model(snapshots: list[DecisionSnapshot], character: str) -> TrainedRecommender:
    character_snapshots = [snapshot for snapshot in snapshots if snapshot.character == character]
    rows = candidate_rows(character_snapshots)
    labels = [label for _, label in rows]
    if len(set(labels)) < 2:
        raise ValueError("training requires at least two classes")
    pipeline = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("classifier", DecisionTreeClassifier(random_state=0)),
        ]
    )
    pipeline.fit([features for features, _ in rows], labels)
    return TrainedRecommender(character=character, pipeline=pipeline)


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
            loss = loss + 0.5 * value_loss(output.value, batch["outcome_values"])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    model.eval()
    return TorchTrainedRecommender(character=character, catalog=dataset.catalog, model=model.cpu())


def save_model(model: TrainedRecommender | TorchTrainedRecommender, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model, TorchTrainedRecommender):
        _save_torch_model(model, path)
        return
    joblib.dump(model, path)


def load_model(path: Path) -> TrainedRecommender | TorchTrainedRecommender:
    if path.suffix == ".pt":
        return _load_torch_model(path)
    return joblib.load(path)


def recommend(model: TrainedRecommender | TorchTrainedRecommender, snapshot: DecisionSnapshot) -> Recommendation:
    if isinstance(model, TorchTrainedRecommender):
        return _recommend_torch(model, snapshot)
    if snapshot.character != model.character:
        raise ValueError(f"snapshot character {snapshot.character!r} does not match model character {model.character!r}")
    features = [_features_for_option(snapshot, option) for option in snapshot.options]
    positive_index = list(model.pipeline.classes_).index(1)
    scores = model.pipeline.predict_proba(features)[:, positive_index]
    candidates = [
        CandidateRecommendation(
            option_id=option.id,
            action="skip" if option.kind == "skip" else "pick",
            score=float(score),
        )
        for option, score in zip(snapshot.options, scores, strict=True)
    ]
    ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    return Recommendation(best=ranked[0], candidates=ranked)


def _features_for_option(snapshot: DecisionSnapshot, option: ChoiceOption) -> FeatureRow:
    return _unlabeled_features(snapshot, option)


def _unlabeled_features(snapshot: DecisionSnapshot, option: ChoiceOption) -> FeatureRow:
    return {
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
        **{f"tag:{tag}": 1 for tag in option.tags},
        **{f"relic:{relic}": 1 for relic in snapshot.relics},
    }


def _recommend_torch(model: TorchTrainedRecommender, snapshot: DecisionSnapshot) -> Recommendation:
    import torch

    if snapshot.character != model.character:
        raise ValueError(f"snapshot character {snapshot.character!r} does not match model character {model.character!r}")
    step = GameStep.from_legacy_snapshot(snapshot, catalog_version=model.catalog.version)
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
    candidates = [
        CandidateRecommendation(
            option_id=option.id,
            action="skip" if option.kind == "skip" else "pick",
            score=float(score),
        )
        for option, score in zip(snapshot.options, scores, strict=True)
    ]
    ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    return Recommendation(best=ranked[0], candidates=ranked)


def _step_with_query_label(step: GameStep) -> GameStep:
    return GameStep(
        state=step.state,
        actions=step.actions,
        chosen_action_id=step.actions[0].identity,
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

    checkpoint: dict[str, Any] = torch.load(path, map_location="cpu", weights_only=False)
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
