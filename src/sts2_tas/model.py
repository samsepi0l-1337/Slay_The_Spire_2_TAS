from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from .dataset import FeatureRow, candidate_rows
from .schema import ChoiceOption, DecisionSnapshot


@dataclass(frozen=True)
class TrainedRecommender:
    character: str
    pipeline: Pipeline


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


def save_model(model: TrainedRecommender, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: Path) -> TrainedRecommender:
    return joblib.load(path)


def recommend(model: TrainedRecommender, snapshot: DecisionSnapshot) -> Recommendation:
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
