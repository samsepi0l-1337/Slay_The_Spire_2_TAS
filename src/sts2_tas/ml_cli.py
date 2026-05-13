from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import load_snapshots
from .model import load_model, recommend, save_model, train_model, train_torch_model
from .schema import DecisionSnapshot, GameStep
from .torch_dataset import load_game_steps, write_game_steps


def add_ml_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    train = subparsers.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--model", type=Path, required=True)
    train.add_argument("--character", required=True)
    train.add_argument("--backend", choices=["sklearn", "torch"], default="sklearn")
    train.add_argument("--epochs", type=int, default=30)
    train.add_argument("--batch-size", type=int, default=128)
    train.add_argument("--device", default="auto")
    train.set_defaults(handler=_train)

    recommend_parser = subparsers.add_parser("recommend")
    recommend_parser.add_argument("--model", type=Path, required=True)
    recommend_parser.add_argument("--snapshot", type=Path, required=True)
    recommend_parser.add_argument("--backend", choices=["auto", "sklearn", "torch"], default="auto")
    recommend_parser.set_defaults(handler=_recommend)

    migrate_dataset = subparsers.add_parser("migrate-dataset")
    migrate_dataset.add_argument("--in", dest="source", type=Path, required=True)
    migrate_dataset.add_argument("--out", type=Path, required=True)
    migrate_dataset.add_argument("--catalog-version", default="local")
    migrate_dataset.set_defaults(handler=_migrate_dataset)


def _train(args: argparse.Namespace) -> None:
    if args.backend == "torch":
        model = train_torch_model(
            load_game_steps(args.dataset),
            character=args.character,
            epochs=args.epochs,
            batch_size=args.batch_size,
            device=args.device,
        )
    else:
        model = train_model(load_snapshots(args.dataset), character=args.character)
    save_model(model, args.model)


def _recommend(args: argparse.Namespace) -> None:
    snapshot = DecisionSnapshot.from_json(args.snapshot.read_text(encoding="utf-8"))
    result = recommend(_load_model_for_backend(args.model, args.backend), snapshot)
    print(
        json.dumps(
            {
                "best": {
                    "option_id": result.best.option_id,
                    "action": result.best.action,
                    "score": result.best.score,
                },
                "candidates": [
                    {"option_id": candidate.option_id, "action": candidate.action, "score": candidate.score}
                    for candidate in result.candidates
                ],
            },
            sort_keys=True,
        )
    )


def _migrate_dataset(args: argparse.Namespace) -> None:
    write_game_steps(
        args.out,
        [GameStep.from_legacy_snapshot(snapshot, catalog_version=args.catalog_version) for snapshot in load_snapshots(args.source)],
    )


def _load_model_for_backend(path: Path, backend: str):
    if backend == "sklearn" and path.suffix == ".pt":
        raise ValueError("sklearn backend cannot load .pt torch models")
    if backend == "torch" and path.suffix != ".pt":
        raise ValueError("torch backend expects a .pt model")
    return load_model(path)
