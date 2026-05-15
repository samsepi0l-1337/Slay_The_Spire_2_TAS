from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import load_model, recommend, save_model, train_torch_model
from .schema import GameStep
from .tas_experience import load_tas_experiences, supervised_training_experiences
from .torch_dataset import load_game_steps


def add_ml_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    train = subparsers.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--model", type=Path)
    train.add_argument("--character")
    train.add_argument("--label-policy", choices=["legacy", "verified"], default="legacy")
    train.add_argument("--epochs", type=int, default=30)
    train.add_argument("--batch-size", type=int, default=128)
    train.add_argument("--device", default="auto")
    train.set_defaults(handler=_train)

    recommend_parser = subparsers.add_parser("recommend")
    recommend_parser.add_argument("--model", type=Path, required=True)
    recommend_parser.add_argument("--step", type=Path, required=True)
    recommend_parser.set_defaults(handler=_recommend)


def _train(args: argparse.Namespace) -> None:
    if args.label_policy == "verified":
        experiences = load_tas_experiences(args.dataset)
        trainable = supervised_training_experiences(experiences)
        print(
            json.dumps(
                {
                    "label_policy": "verified",
                    "rows": len(experiences),
                    "trainable_rows": len(trainable),
                    "excluded_rows": len(experiences) - len(trainable),
                    "trained": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.model is None or args.character is None:
        raise ValueError("legacy torch training requires --model and --character")
    if args.model.suffix != ".pt":
        raise ValueError("torch training expects --model to end with .pt")
    model = train_torch_model(
        load_game_steps(args.dataset),
        character=args.character,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
    )
    save_model(model, args.model)


def _recommend(args: argparse.Namespace) -> None:
    step = GameStep.from_json(args.step.read_text(encoding="utf-8"))
    result = recommend(load_model(args.model), step)
    print(
        json.dumps(
            {
                "best": _candidate_to_dict(result.best),
                "candidates": [_candidate_to_dict(candidate) for candidate in result.candidates],
            },
            sort_keys=True,
        )
    )


def _candidate_to_dict(candidate) -> dict[str, str | float | None]:
    return {
        "action_id": candidate.action_id,
        "action_type": candidate.action_type,
        "option_id": candidate.option_id,
        "score": candidate.score,
    }
