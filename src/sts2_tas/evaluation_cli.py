from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import model_evaluation_metrics, play_evaluation_metrics
from .model import load_model, recommend
from .torch_dataset import load_game_steps
from .trajectory import supervised_training_steps


def add_evaluation_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    evaluate_model = subparsers.add_parser("evaluate-model")
    evaluate_model.add_argument("--dataset", type=Path, required=True)
    evaluate_model.add_argument("--model", type=Path, required=True)
    evaluate_model.add_argument("--character", required=True)
    evaluate_model.add_argument("--out", type=Path, required=True)
    evaluate_model.set_defaults(handler=_evaluate_model)

    evaluate_play = subparsers.add_parser("evaluate-play")
    evaluate_play.add_argument("--episodes", type=Path, required=True)
    evaluate_play.add_argument("--out", type=Path, required=True)
    evaluate_play.set_defaults(handler=_evaluate_play)


def _evaluate_model(args: argparse.Namespace) -> None:
    model = load_model(args.model)
    steps = [
        step
        for step in supervised_training_steps(load_game_steps(args.dataset))
        if step.state.character == args.character
    ]
    _write_json(args.out, model_evaluation_metrics((step, recommend(model, step)) for step in steps))


def _evaluate_play(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in args.episodes.read_text(encoding="utf-8").splitlines() if line.strip()]
    _write_json(args.out, play_evaluation_metrics(rows))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
