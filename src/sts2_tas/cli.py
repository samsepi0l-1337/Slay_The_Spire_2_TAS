from __future__ import annotations

import argparse
import json
from pathlib import Path

from .automation import JsonlInputController, apply_action, plan_action
from .dataset import append_snapshot, load_snapshots, write_snapshots
from .evaluation import write_evaluation
from .model import load_model, recommend, save_model, train_model
from .recognition import (
    DetectionKind,
    FakeOcrProvider,
    OcrProvider,
    OcrToken,
    ScreenDetection,
    TesseractOcrProvider,
    detect_screen,
    parse_ocr_screen,
)
from .runtime import backup_save, restore_save, run_seed_loop
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

    parse_screen = subparsers.add_parser("parse-screen")
    parse_screen.add_argument("--screenshot", type=Path, required=True)
    parse_screen.add_argument("--ocr-fixture", type=Path)
    parse_screen.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    parse_screen.add_argument("--ocr-language", default="eng+kor")
    parse_screen.add_argument("--out", type=Path, required=True)
    parse_screen.set_defaults(handler=_parse_screen)

    capture_live = subparsers.add_parser("capture-live")
    capture_live.add_argument("--capture-fixture", type=Path, required=True)
    capture_live.add_argument("--ocr-fixture", type=Path)
    capture_live.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    capture_live.add_argument("--ocr-language", default="eng+kor")
    capture_live.add_argument("--out", type=Path, required=True)
    capture_live.add_argument("--game-version", required=True)
    capture_live.add_argument("--branch", required=True)
    capture_live.add_argument("--character", required=True)
    capture_live.add_argument("--ascension", type=int, required=True)
    capture_live.add_argument("--floor", type=int, required=True)
    capture_live.add_argument("--deck", default="")
    capture_live.add_argument("--relics", default="")
    capture_live.add_argument("--hp", type=int, required=True)
    capture_live.add_argument("--gold", type=int, required=True)
    capture_live.set_defaults(handler=_capture_live)

    act = subparsers.add_parser("act")
    act.add_argument("--snapshot", type=Path, required=True)
    act.add_argument("--choice", required=True)
    act.add_argument("--input-log", type=Path, required=True)
    act.add_argument("--execute", action="store_true")
    act.set_defaults(handler=_act)

    save_state = subparsers.add_parser("save-state")
    save_state_subparsers = save_state.add_subparsers(required=True)
    save_backup = save_state_subparsers.add_parser("backup")
    save_backup.add_argument("--save", type=Path, required=True)
    save_backup.add_argument("--backup-dir", type=Path, required=True)
    save_backup.set_defaults(handler=_save_state_backup)
    save_restore = save_state_subparsers.add_parser("restore")
    save_restore.add_argument("--save", type=Path, required=True)
    save_restore.add_argument("--backup-dir", type=Path, required=True)
    save_restore.set_defaults(handler=_save_state_restore)

    run_loop = subparsers.add_parser("run-loop")
    run_loop.add_argument("--seeds", required=True)
    run_loop.add_argument("--capture-fixture", type=Path, required=True)
    run_loop.add_argument("--ocr-fixture", type=Path)
    run_loop.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    run_loop.add_argument("--ocr-language", default="eng+kor")
    run_loop.add_argument("--episodes-out", type=Path, required=True)
    run_loop.add_argument("--max-steps", type=int, required=True)
    run_loop.set_defaults(handler=_run_loop)

    evaluate_seeds = subparsers.add_parser("evaluate-seeds")
    evaluate_seeds.add_argument("--episodes", type=Path, required=True)
    evaluate_seeds.add_argument("--out", type=Path, required=True)
    evaluate_seeds.set_defaults(handler=_evaluate_seeds)
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


def _parse_screen(args: argparse.Namespace) -> None:
    parsed = parse_ocr_screen(args.screenshot, _ocr_provider(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(parsed.to_dict(), sort_keys=True), encoding="utf-8")


def _capture_live(args: argparse.Namespace) -> None:
    parsed = parse_ocr_screen(args.capture_fixture, _ocr_provider(args))
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
        options=[option.to_choice_option() for option in parsed.options],
        chosen=None,
        skipped=False,
        screenshot_path=args.capture_fixture,
    )
    append_snapshot(args.out, snapshot)


def _act(args: argparse.Namespace) -> None:
    snapshot = DecisionSnapshot.from_json(args.snapshot.read_text(encoding="utf-8"))
    action = plan_action(snapshot, _parse_choice(args.choice), dry_run=not args.execute)
    controller = JsonlInputController(args.input_log) if args.execute else None
    report = apply_action(action, controller)
    print(json.dumps(report, sort_keys=True))


def _save_state_backup(args: argparse.Namespace) -> None:
    backup_save(args.save, args.backup_dir)


def _save_state_restore(args: argparse.Namespace) -> None:
    restore_save(args.save, args.backup_dir)


def _run_loop(args: argparse.Namespace) -> None:
    run_seed_loop(
        seeds=[int(seed) for seed in args.seeds.split(",") if seed],
        screenshot=args.capture_fixture,
        ocr_provider=_ocr_provider(args),
        episodes_out=args.episodes_out,
        max_steps=args.max_steps,
    )


def _evaluate_seeds(args: argparse.Namespace) -> None:
    write_evaluation(args.episodes, args.out)


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


def _ocr_provider(args: argparse.Namespace) -> OcrProvider:
    if args.ocr_provider == "tesseract":
        return TesseractOcrProvider(language=args.ocr_language)
    if args.ocr_fixture is None:
        raise ValueError("ocr fixture is required for fixture OCR provider")
    return _fixture_ocr_provider(args.ocr_fixture)


def _fixture_ocr_provider(path: Path) -> FakeOcrProvider:
    return FakeOcrProvider(
        [
            OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
            for row in json.loads(path.read_text(encoding="utf-8"))
        ]
    )
