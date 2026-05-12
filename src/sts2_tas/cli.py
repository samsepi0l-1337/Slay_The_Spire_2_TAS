from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import append_snapshot, load_snapshots, write_snapshots
from .model import load_model, recommend, save_model, train_model
from .recognition import DetectionKind, ScreenDetection, detect_screen
from .schema import ChoiceOption, DecisionChoice, DecisionSnapshot


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    args.handler(args)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sts2-tas")
    subparsers = parser.add_subparsers(required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--screenshot", type=Path, required=True)
    capture.add_argument("--out", type=Path, required=True)
    capture.add_argument("--game-version", required=True)
    capture.add_argument("--branch", required=True)
    capture.add_argument("--character", required=True)
    capture.add_argument("--ascension", type=int, required=True)
    capture.add_argument("--floor", type=int, required=True)
    capture.add_argument("--deck", default="")
    capture.add_argument("--relics", default="")
    capture.add_argument("--hp", type=int, required=True)
    capture.add_argument("--gold", type=int, required=True)
    capture.set_defaults(handler=_capture)

    label = subparsers.add_parser("label")
    label.add_argument("--dataset", type=Path, required=True)
    label.add_argument("--index", type=int, required=True)
    label.add_argument("--choice", required=True)
    label.set_defaults(handler=_label)

    train = subparsers.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--model", type=Path, required=True)
    train.add_argument("--character", required=True)
    train.set_defaults(handler=_train)

    recommend_parser = subparsers.add_parser("recommend")
    recommend_parser.add_argument("--model", type=Path, required=True)
    recommend_parser.add_argument("--snapshot", type=Path, required=True)
    recommend_parser.set_defaults(handler=_recommend)
    return parser


def _capture(args: argparse.Namespace) -> None:
    detection = detect_screen(args.screenshot)
    if detection.kind is DetectionKind.UNKNOWN:
        raise ValueError(f"unknown screen layout for {args.screenshot}")
    options = _options_from_detection(detection)
    snapshot = DecisionSnapshot(
        game_version=args.game_version,
        branch=args.branch,
        character=args.character,
        ascension=args.ascension,
        floor=args.floor,
        deck=_split_csv(args.deck),
        relics=_split_csv(args.relics),
        hp=args.hp,
        gold=args.gold,
        options=options,
        chosen=None,
        skipped=False,
        screenshot_path=args.screenshot,
    )
    append_snapshot(args.out, snapshot)


def _label(args: argparse.Namespace) -> None:
    snapshots = load_snapshots(args.dataset)
    target = snapshots[args.index]
    choice = _parse_choice(args.choice)
    _validate_choice(target, choice)
    snapshots[args.index] = DecisionSnapshot(
        game_version=target.game_version,
        branch=target.branch,
        character=target.character,
        ascension=target.ascension,
        floor=target.floor,
        deck=target.deck,
        relics=target.relics,
        hp=target.hp,
        gold=target.gold,
        options=target.options,
        chosen=choice,
        skipped=choice.action == "skip",
        screenshot_path=target.screenshot_path,
    )
    write_snapshots(args.dataset, snapshots)


def _train(args: argparse.Namespace) -> None:
    save_model(train_model(load_snapshots(args.dataset), character=args.character), args.model)


def _recommend(args: argparse.Namespace) -> None:
    result = recommend(load_model(args.model), DecisionSnapshot.from_json(args.snapshot.read_text(encoding="utf-8")))
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


def _parse_choice(choice: str) -> DecisionChoice:
    if choice == "skip":
        return DecisionChoice(action="skip")
    action, option_id = choice.split(":", maxsplit=1)
    return DecisionChoice(action=action, option_id=option_id)


def _validate_choice(snapshot: DecisionSnapshot, choice: DecisionChoice) -> None:
    if choice.action == "pick" and choice.option_id not in {option.id for option in snapshot.options}:
        raise ValueError(f"choice option_id is not present in snapshot options: {choice.option_id}")
    if choice.action == "skip" and not any(option.kind == "skip" for option in snapshot.options):
        raise ValueError("skip choice requires a skip option in the snapshot")


def _options_from_detection(detection: ScreenDetection) -> list[ChoiceOption]:
    if detection.kind is DetectionKind.CARD_REWARD:
        return [
            *[
                ChoiceOption(id=f"card_{index}", name=f"Card {index}", kind="card", tags=[])
                for index, _ in enumerate(detection.option_boxes, start=1)
            ],
            ChoiceOption(id="skip", name="Skip", kind="skip", tags=[]),
        ]
    return [
        ChoiceOption(id=f"relic_{index}", name=f"Relic {index}", kind="relic", tags=[])
        for index, _ in enumerate(detection.option_boxes, start=1)
    ]


def _split_csv(value: str) -> list[str]:
    return [item for item in value.split(",") if item]
