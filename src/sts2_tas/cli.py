from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from .automation import DeferredJsonlInputController, JsonlInputController, NativeInputController, apply_action, plan_action
from .capture_state import load_captured_game_state
from .cv_calibration import RegionCalibration, load_region_calibration
from .json_io import load_json_file
from .evaluation import write_evaluation_report
from .evaluation_cli import add_evaluation_parsers
from .live_learning import run_live_learn_loop
from .ml_cli import add_ml_parsers
from .ml_entities import resolve_action_identity
from .model import load_model, recommend
from .recognition import FakeOcrProvider, OcrProvider, OcrToken, TesseractOcrProvider, detect_screen, parse_ocr_screen
from .runtime import backup_save, capture_screen, restore_save, run_seed_loop
from .schema import CoordinateSpace, GameStep, TargetWindow
from .step_factory import PerceptionQualityError, game_step_from_detection, game_step_from_parsed_screen
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
    add_evaluation_parsers(subparsers)

    parse_screen = subparsers.add_parser("parse-screen")
    parse_screen.add_argument("--screenshot", type=Path, required=True)
    parse_screen.add_argument("--ocr-fixture", type=Path)
    parse_screen.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    parse_screen.add_argument("--ocr-language", default="eng+kor")
    parse_screen.add_argument("--tesseract-binary", default="tesseract")
    parse_screen.add_argument("--tessdata-dir", type=Path)
    parse_screen.add_argument("--ocr-psm", type=int)
    parse_screen.add_argument("--region-calibration", type=Path)
    parse_screen.add_argument("--out", type=Path, required=True)
    parse_screen.set_defaults(handler=_parse_screen)

    capture_live = subparsers.add_parser("capture-live")
    capture_live.add_argument("--capture-fixture", type=Path, required=True)
    capture_live.add_argument("--ocr-fixture", type=Path)
    capture_live.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    capture_live.add_argument("--ocr-language", default="eng+kor")
    capture_live.add_argument("--tesseract-binary", default="tesseract")
    capture_live.add_argument("--tessdata-dir", type=Path)
    capture_live.add_argument("--ocr-psm", type=int)
    capture_live.add_argument("--region-calibration", type=Path)
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
    live_step.add_argument("--ack-ocr-fixture-sequence", type=Path)
    live_step.add_argument("--ack-live-poll", action="store_true")
    live_step.add_argument("--ack-max-retries", type=int, default=0)
    live_step.add_argument("--failure-log", type=Path)
    live_step.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    live_step.add_argument("--ocr-language", default="eng+kor")
    live_step.add_argument("--tesseract-binary", default="tesseract")
    live_step.add_argument("--tessdata-dir", type=Path)
    live_step.add_argument("--ocr-psm", type=int)
    live_step.add_argument("--region-calibration", type=Path)
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
    live_learn_loop.add_argument("--ack-ocr-fixture-sequence", type=Path)
    live_learn_loop.add_argument("--ack-live-poll", action="store_true")
    live_learn_loop.add_argument("--ack-max-retries", type=int, default=0)
    live_learn_loop.add_argument("--trajectory-out", type=Path)
    live_learn_loop.add_argument("--failure-log", type=Path)
    live_learn_loop.add_argument("--ocr-provider", choices=["fixture", "tesseract"], default="fixture")
    live_learn_loop.add_argument("--ocr-language", default="eng+kor")
    live_learn_loop.add_argument("--tesseract-binary", default="tesseract")
    live_learn_loop.add_argument("--tessdata-dir", type=Path)
    live_learn_loop.add_argument("--ocr-psm", type=int)
    live_learn_loop.add_argument("--region-calibration", type=Path)
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
    run_loop.add_argument("--tesseract-binary", default="tesseract")
    run_loop.add_argument("--tessdata-dir", type=Path)
    run_loop.add_argument("--ocr-psm", type=int)
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
        label_source="human",
    )
    write_game_steps(args.dataset, steps)


def _parse_screen(args: argparse.Namespace) -> None:
    parsed = parse_ocr_screen(args.screenshot, _ocr_provider(args), calibration=_region_calibration(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(parsed.to_dict(), sort_keys=True), encoding="utf-8")


def _capture_live(args: argparse.Namespace) -> None:
    step = _step_from_screen(args, args.capture_fixture)
    append_game_step(args.out, step)


def _live_step(args: argparse.Namespace) -> None:
    _validate_ack_max_retries(args)
    target_window = _target_window(args)
    if args.capture_fixture:
        screenshot_path = args.capture_fixture
    elif target_window is None:
        screenshot_path = capture_screen(args.screenshot_out)
    else:
        screenshot_path = capture_screen(args.screenshot_out, bbox=target_window.bounds.to_bbox())
    coordinate_space: CoordinateSpace = "window_relative" if target_window is not None and not args.capture_fixture else "screen_absolute"
    try:
        step = _step_from_screen(args, screenshot_path)
    except PerceptionQualityError as error:
        if args.failure_log is None:
            raise
        _append_failure_log(
            args.failure_log,
            {
                "reason": "fail_closed_perception",
                "action_id": None,
                "before_signature": None,
                "after_signature": None,
                "retry_count": 0,
                "latency_ms": 0,
                "controller_error": str(error),
            },
        )
        return
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
    start = time.perf_counter()
    try:
        action_report, transition_ack = _apply_live_step_action(
            args,
            step=step,
            action=action,
            action_id=action_id,
            controller=controller,
            screenshot_path=screenshot_path,
            target_window=target_window,
        )
    except Exception as error:
        if args.failure_log is None:
            raise
        before = acknowledge_transition(step, [], action_id)
        _append_live_step_failure(
            args.failure_log,
            reason="controller_error",
            action_id=action_id,
            before_signature=before.before_signature,
            after_signature=None,
            retry_count=0,
            latency_ms=_latency_ms(start),
            controller_error=str(error),
        )
        action_report = action.to_report()
        action_report["controller_error"] = str(error)
        action_report["success"] = False
        transition_ack = None
    report = {
        "choice": _automation_choice(action),
        "action": action_report,
        "input_plan": action.input_plan(),
        "screenshot_path": str(screenshot_path),
    }
    if transition_ack is not None:
        report["transition_ack"] = transition_ack
        if transition_ack.get("status") in {"no_op", "timeout"}:
            _append_live_step_failure(
                args.failure_log,
                reason=str(transition_ack["status"]),
                action_id=action_id,
                before_signature=_optional_str(transition_ack.get("before_signature")),
                after_signature=_optional_str(transition_ack.get("after_signature")),
                retry_count=int(transition_ack.get("retry_count", 0)),
                latency_ms=_latency_ms(start),
                controller_error=None,
            )
            report["failure"] = {"reason": transition_ack["status"]}
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
    parsed = parse_ocr_screen(screenshot_path, ocr_provider, calibration=_region_calibration(args))
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
        kwargs = (
            {"language": args.ocr_language, "tessdata_dir": args.tessdata_dir}
            | ({"binary": args.tesseract_binary} if args.tesseract_binary != "tesseract" else {})
            | ({"page_segmentation_mode": args.ocr_psm} if args.ocr_psm is not None else {})
        )
        return TesseractOcrProvider(**kwargs)
    if args.ocr_fixture is None:
        raise ValueError("ocr fixture is required for fixture OCR provider")
    return _fixture_ocr_provider(args.ocr_fixture)


def _fixture_ocr_provider(path: Path) -> FakeOcrProvider:
    return FakeOcrProvider(
        [
            OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
            for row in load_json_file(path)
        ]
    )


def _region_calibration(args: argparse.Namespace) -> RegionCalibration | None:
    if getattr(args, "region_calibration", None) is None:
        return None
    return load_region_calibration(args.region_calibration)


def _apply_live_step_action(
    args: argparse.Namespace,
    *,
    step: GameStep,
    action,
    action_id: str,
    controller,
    screenshot_path: Path,
    target_window: TargetWindow | None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    _validate_ack_max_retries(args)
    if args.ack_ocr_fixture_sequence is None and not args.ack_live_poll:
        if args.ack_ocr_fixture is None:
            action_report = apply_action(action, controller)
            return action_report, None
        deferred_controller = _deferred_input_controller(controller)
        try:
            action_report = apply_action(action, deferred_controller)
            ack_step = _step_from_screen_with_provider(args, screenshot_path, _fixture_ocr_provider(args.ack_ocr_fixture))
            ack = acknowledge_transition(step, [ack_step], action_id)
            _finish_deferred_input(deferred_controller, changed=ack.status == "changed")
            return action_report, asdict(ack)
        except Exception:
            _finish_deferred_input(deferred_controller, changed=False)
            raise

    history: list[dict[str, object]] = []
    action_report: dict[str, object] = {}
    deferred_controller = _deferred_input_controller(controller)
    try:
        action_report = apply_action(action, deferred_controller)
        for attempt in range(1, args.ack_max_retries + 2):
            ack_step = _ack_poll_step(args, screenshot_path, attempt, target_window)
            ack = acknowledge_transition(step, [] if ack_step is None else [ack_step], action_id)
            ack_report = asdict(ack)
            history.append(ack_report)
            if not ack.retry_recommended:
                break
        final = dict(history[-1])
        final["attempts"] = len(history)
        final["retry_count"] = len(history) - 1
        final["history"] = history
        _finish_deferred_input(deferred_controller, changed=final.get("status") == "changed")
        return action_report, final
    except Exception:
        _finish_deferred_input(deferred_controller, changed=False)
        raise


def _deferred_input_controller(controller):
    controller_type = JsonlInputController
    if isinstance(controller_type, type) and isinstance(controller, controller_type):
        return DeferredJsonlInputController(controller.log_path)
    return controller


def _finish_deferred_input(controller, *, changed: bool) -> None:
    if isinstance(controller, DeferredJsonlInputController):
        if changed:
            controller.commit()
        else:
            controller.rollback()


def _validate_ack_max_retries(args: argparse.Namespace) -> None:
    if getattr(args, "ack_max_retries", 0) < 0:
        raise ValueError("--ack-max-retries must be non-negative")


def _ack_poll_step(
    args: argparse.Namespace,
    screenshot_path: Path,
    attempt: int,
    target_window: TargetWindow | None,
) -> GameStep | None:
    if args.ack_ocr_fixture_sequence is not None:
        return _ack_fixture_sequence_step(args, screenshot_path, attempt)
    return _ack_live_poll_step(args, attempt, target_window)


def _ack_fixture_sequence_step(args: argparse.Namespace, screenshot_path: Path, attempt: int) -> GameStep | None:
    frames = load_json_file(args.ack_ocr_fixture_sequence)
    if attempt > len(frames):
        return None
    provider = FakeOcrProvider(_frame_tokens(frames[attempt - 1]))
    return _step_from_screen_with_provider(args, screenshot_path, provider)


def _ack_live_poll_step(
    args: argparse.Namespace,
    attempt: int,
    target_window: TargetWindow | None,
) -> GameStep | None:
    if args.screenshot_out is None:
        return None
    ack_path = args.screenshot_out.with_name(f"{args.screenshot_out.stem}-ack-{attempt:06d}{args.screenshot_out.suffix}")
    if target_window is None:
        screenshot_path = capture_screen(ack_path)
    else:
        screenshot_path = capture_screen(ack_path, bbox=target_window.bounds.to_bbox())
    return _step_from_screen(args, screenshot_path)


def _frame_tokens(frame) -> list[OcrToken]:
    return [
        OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
        for row in frame
    ]


def _append_failure_log(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")


def _append_live_step_failure(
    path: Path | None,
    *,
    reason: str,
    action_id: str | None,
    before_signature: str | None,
    after_signature: str | None,
    retry_count: int,
    latency_ms: int,
    controller_error: str | None,
) -> None:
    if path is None:
        return
    row: dict[str, object] = {
        "reason": reason,
        "action_id": action_id,
        "before_signature": before_signature,
        "after_signature": after_signature,
        "retry_count": retry_count,
        "latency_ms": latency_ms,
    }
    if controller_error is not None:
        row["controller_error"] = controller_error
    _append_failure_log(path, row)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
