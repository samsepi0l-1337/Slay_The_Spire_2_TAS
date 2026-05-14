from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .automation import JsonlInputController, NativeInputController, apply_action, plan_action
from .capture_state import load_captured_game_state
from .evaluation import write_evaluation_report
from .live_learning import run_live_learn_loop
from .ml_cli import add_ml_parsers
from .ml_entities import resolve_action_identity
from .model import load_model, recommend
from .recognition import FakeOcrProvider, OcrProvider, OcrToken, TesseractOcrProvider, detect_screen, parse_ocr_screen
from .runtime import backup_save, capture_screen, restore_save, run_seed_loop
from .schema import CoordinateSpace, GameStep, TargetWindow
from .step_factory import game_step_from_detection, game_step_from_parsed_screen
from .torch_dataset import append_game_step, load_game_steps, write_game_steps
from .transition import acknowledge_transition
from .windowing import WindowDetector


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
    _add_state_args(capture)
    capture.set_defaults(handler=_capture)

    label = subparsers.add_parser("label")
    label.add_argument("--dataset", type=Path, required=True)
    label.add_argument("--index", type=int, required=True)
    label.add_argument("--choice", required=True)
    label.set_defaults(handler=_label)

    add_ml_parsers(subparsers)

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
    _add_state_args(capture_live)
    capture_live.set_defaults(handler=_capture_live)

    live_step = subparsers.add_parser("live-step")
    capture_source = live_step.add_mutually_exclusive_group(required=True)
    capture_source.add_argument("--capture-fixture", type=Path)
    capture_source.add_argument("--screenshot-out", type=Path)
    decision_source = live_step.add_mutually_exclusive_group(required=True)
    decision_source.add_argument("--choice")
    decision_source.add_argument("--model", type=Path)
    live_step.add_argument("--ocr-fixture", type=Path)
    live_step.add_argument("--ack-ocr-fixture", type=Path)
    live_step.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    live_step.add_argument("--ocr-language", default="eng+kor")
    live_step.add_argument("--input-log", type=Path, required=True)
    live_step.add_argument("--input-backend", choices=["jsonl", "native"], default="jsonl")
    live_step.add_argument("--execute", action="store_true")
    live_step.add_argument("--target-process")
    live_step.add_argument("--game-version", required=True)
    live_step.add_argument("--branch", required=True)
    live_step.add_argument("--character", required=True)
    live_step.add_argument("--ascension", type=int, required=True)
    live_step.add_argument("--floor", type=int, required=True)
    _add_state_args(live_step)
    live_step.set_defaults(handler=_live_step)

    live_learn_loop = subparsers.add_parser("live-learn-loop")
    live_learn_source = live_learn_loop.add_mutually_exclusive_group(required=True)
    live_learn_source.add_argument("--capture-fixture", type=Path)
    live_learn_source.add_argument("--screenshot-out", type=Path)
    live_learn_decision = live_learn_loop.add_mutually_exclusive_group(required=True)
    live_learn_decision.add_argument("--choice")
    live_learn_decision.add_argument("--model", type=Path)
    live_learn_loop.add_argument("--dataset", type=Path, required=True)
    live_learn_loop.add_argument("--max-steps", type=int)
    live_learn_loop.add_argument("--ocr-fixture", type=Path)
    live_learn_loop.add_argument("--ocr-fixture-sequence", type=Path)
    live_learn_loop.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    live_learn_loop.add_argument("--ocr-language", default="eng+kor")
    live_learn_loop.add_argument("--input-log", type=Path, required=True)
    live_learn_loop.add_argument("--input-backend", choices=["jsonl", "native"], default="jsonl")
    live_learn_loop.add_argument("--execute", action="store_true")
    live_learn_loop.add_argument("--target-process")
    live_learn_loop.add_argument("--allow-model-self-labels", action="store_true")
    live_learn_loop.add_argument("--train-every", type=int)
    live_learn_loop.add_argument("--model-out", type=Path)
    live_learn_loop.add_argument("--episodes-out", type=Path)
    live_learn_loop.add_argument("--epochs", type=int, default=30)
    live_learn_loop.add_argument("--batch-size", type=int, default=128)
    live_learn_loop.add_argument("--device", default="auto")
    live_learn_loop.add_argument("--game-version", required=True)
    live_learn_loop.add_argument("--branch", required=True)
    live_learn_loop.add_argument("--character", required=True)
    live_learn_loop.add_argument("--ascension", type=int, required=True)
    live_learn_loop.add_argument("--floor", type=int, required=True)
    _add_state_args(live_learn_loop)
    live_learn_loop.set_defaults(handler=_live_learn_loop)
    act = subparsers.add_parser("act")
    act.add_argument("--step", type=Path, required=True)
    act.add_argument("--choice", required=True)
    act.add_argument("--input-log", type=Path, required=True)
    act.add_argument("--input-backend", choices=["jsonl", "native"], default="jsonl")
    act.add_argument("--execute", action="store_true")
    act.add_argument("--target-process")
    act.add_argument("--coordinate-space", choices=["screen_absolute", "window_relative"], default="screen_absolute")
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
    run_loop.add_argument("--victory-seeds", default="")
    run_loop.set_defaults(handler=_run_loop)

    evaluate_seeds = subparsers.add_parser("evaluate-seeds")
    evaluate_seeds.add_argument("--episodes", type=Path, required=True)
    evaluate_seeds.add_argument("--baseline", type=Path)
    evaluate_seeds.add_argument("--out", type=Path, required=True)
    evaluate_seeds.set_defaults(handler=_evaluate_seeds)
    return parser


def _add_state_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-json", type=Path)
    parser.add_argument("--deck", default="")
    parser.add_argument("--relics", default="")
    parser.add_argument("--hp", type=int, required=True)
    parser.add_argument("--gold", type=int, required=True)
    parser.add_argument("--max-hp", type=int)
    parser.add_argument("--block", type=int)
    parser.add_argument("--energy", type=int)
    parser.add_argument("--turn", type=int)
    parser.add_argument("--strength", type=int)
    parser.add_argument("--dexterity", type=int)
    parser.add_argument("--vulnerable", type=int)
    parser.add_argument("--weak", type=int)
    parser.add_argument("--frail", type=int)
    parser.add_argument("--artifact", type=int)
    parser.add_argument("--poison", type=int)
    parser.add_argument("--regen", type=int)
    parser.add_argument("--intangible", type=int)


def _capture(args: argparse.Namespace) -> None:
    detection = detect_screen(args.screenshot)
    step = game_step_from_detection(
        detection=detection,
        game_version=args.game_version,
        branch=args.branch,
        character=args.character,
        ascension=args.ascension,
        floor=args.floor,
        captured_state=_captured_state(args),
        screenshot_path=args.screenshot,
    )
    append_game_step(args.out, step)


def _label(args: argparse.Namespace) -> None:
    steps = load_game_steps(args.dataset)
    target = steps[args.index]
    action_id = _resolve_action_id(target, args.choice)
    steps[args.index] = GameStep(
        state=target.state,
        actions=target.actions,
        chosen_action_id=action_id,
        outcome=target.outcome,
        observation=target.observation,
        screenshot_path=target.screenshot_path,
    )
    write_game_steps(args.dataset, steps)


def _parse_screen(args: argparse.Namespace) -> None:
    parsed = parse_ocr_screen(args.screenshot, _ocr_provider(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(parsed.to_dict(), sort_keys=True), encoding="utf-8")


def _capture_live(args: argparse.Namespace) -> None:
    step = _step_from_screen(args, args.capture_fixture)
    append_game_step(args.out, step)


def _live_step(args: argparse.Namespace) -> None:
    target_window = _target_window(args)
    if args.capture_fixture:
        screenshot_path = args.capture_fixture
    elif target_window is None:
        screenshot_path = capture_screen(args.screenshot_out)
    else:
        screenshot_path = capture_screen(args.screenshot_out, bbox=target_window.bounds.to_bbox())
    coordinate_space: CoordinateSpace = "window_relative" if target_window is not None and not args.capture_fixture else "screen_absolute"
    step = _step_from_screen(args, screenshot_path)
    action_id = _live_step_action_id(args, step)
    action = plan_action(
        step,
        action_id,
        dry_run=not args.execute,
        target_window=target_window,
        coordinate_space=coordinate_space,
    )
    if args.input_backend == "native" and not args.execute:
        raise ValueError("native input backend requires --execute")
    controller = _input_controller(args) if args.execute else None
    report = {
        "choice": _automation_choice(action),
        "action": apply_action(action, controller),
        "input_plan": action.input_plan(),
        "screenshot_path": str(screenshot_path),
    }
    if args.ack_ocr_fixture is not None:
        ack_step = _step_from_screen_with_provider(args, screenshot_path, _fixture_ocr_provider(args.ack_ocr_fixture))
        report["transition_ack"] = asdict(acknowledge_transition(step, [ack_step], action_id))
    if target_window is not None:
        report["target_window"] = target_window.to_dict()
    print(json.dumps(report, sort_keys=True))


def _live_learn_loop(args: argparse.Namespace) -> None:
    print(json.dumps(run_live_learn_loop(args).to_dict(), sort_keys=True))


def _act(args: argparse.Namespace) -> None:
    step = GameStep.from_json(args.step.read_text(encoding="utf-8"))
    if args.target_process is not None and args.coordinate_space != "window_relative":
        raise ValueError("act --target-process requires --coordinate-space window_relative")
    target_window = _target_window(args)
    action_id = _resolve_action_id(step, args.choice)
    action = plan_action(
        step,
        action_id,
        dry_run=not args.execute,
        target_window=target_window,
        coordinate_space=args.coordinate_space,
    )
    if args.input_backend == "native" and not args.execute:
        raise ValueError("native input backend requires --execute")
    controller = _input_controller(args) if args.execute else None
    report = apply_action(action, controller)
    print(json.dumps(report, sort_keys=True))


def _input_controller(args: argparse.Namespace) -> JsonlInputController | NativeInputController:
    if args.input_backend == "native":
        return NativeInputController()
    return JsonlInputController(args.input_log)


def _target_window(args: argparse.Namespace) -> TargetWindow | None:
    if getattr(args, "target_process", None) is None:
        return None
    return WindowDetector().detect(args.target_process)


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
        victory_seeds={int(seed) for seed in args.victory_seeds.split(",") if seed},
    )


def _evaluate_seeds(args: argparse.Namespace) -> None:
    write_evaluation_report(args.episodes, args.out, baseline=args.baseline)


def _step_from_screen(
    args: argparse.Namespace,
    screenshot_path: Path,
) -> GameStep:
    return _step_from_screen_with_provider(args, screenshot_path, _ocr_provider(args))


def _step_from_screen_with_provider(
    args: argparse.Namespace,
    screenshot_path: Path,
    ocr_provider: OcrProvider,
) -> GameStep:
    parsed = parse_ocr_screen(screenshot_path, ocr_provider)
    return game_step_from_parsed_screen(
        parsed=parsed,
        game_version=args.game_version,
        branch=args.branch,
        character=args.character,
        ascension=args.ascension,
        floor=args.floor,
        captured_state=_captured_state(args),
        source_type=args.ocr_provider,
    )


def _live_step_action_id(args: argparse.Namespace, step: GameStep) -> str:
    if args.choice is not None:
        action_id = _resolve_action_id(step, args.choice)
    else:
        result = recommend(load_model(args.model), step)
        action_id = result.best.action_id
    _resolve_action_id(step, action_id)
    return action_id


def _automation_choice(action) -> dict[str, str | None]:
    return {"action": action.action, "option_id": action.option_id}


def _resolve_action_id(step: GameStep, choice: str) -> str:
    try:
        return resolve_action_identity(step.actions, choice)
    except ValueError as error:
        if "not present" in str(error):
            raise ValueError(f"chosen action is not present in legal action candidates: {choice}") from error
        raise


def _split_csv(value: str) -> list[str]:
    return [item for item in value.split(",") if item]


def _captured_state(args: argparse.Namespace):
    return load_captured_game_state(
        state_json=args.state_json,
        deck=_split_csv(args.deck),
        relics=_split_csv(args.relics),
        hp=args.hp,
        gold=args.gold,
        max_hp=args.max_hp,
        block=args.block,
        energy=args.energy,
        turn=args.turn,
        strength=args.strength,
        dexterity=args.dexterity,
        vulnerable=args.vulnerable,
        weak=args.weak,
        frail=args.frail,
        artifact=args.artifact,
        poison=args.poison,
        regen=args.regen,
        intangible=args.intangible,
    )


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
