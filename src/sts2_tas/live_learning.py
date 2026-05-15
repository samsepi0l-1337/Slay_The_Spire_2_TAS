from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .automation import DeferredJsonlInputController, JsonlInputController, NativeInputController, apply_action, plan_action
from .capture_state import load_captured_game_state
from .cv_calibration import load_region_calibration
from .json_io import load_json_file
from .ml_entities import resolve_action_identity
from .model import load_model, recommend, save_model, train_torch_model
from .recognition import FakeOcrProvider, OcrProvider, OcrToken, TesseractOcrProvider, parse_ocr_screen
from .runtime import capture_screen
from .schema import CoordinateSpace, GameStep, StepOutcome, TargetWindow
from .step_factory import PerceptionQualityError, game_step_from_parsed_screen
from .torch_dataset import append_game_step, load_game_steps, write_game_steps
from .trajectory import EpisodeState, TrajectoryStep
from .transition import TransitionAcknowledgement, acknowledge_transition
from .windowing import WindowDetector

GAMEPLAY_CONTEXTS = {"combat", "card_reward", "relic_choice", "map", "shop", "event", "rest"}


@dataclass(frozen=True)
class LiveLearnSummary:
    steps: int
    trained: int
    interrupted: bool
    dataset: str
    model: str | None

    def to_dict(self) -> dict[str, int | bool | str | None]:
        return asdict(self)


def run_live_learn_loop(args: argparse.Namespace) -> LiveLearnSummary:
    if args.input_backend == "native" and not args.execute:
        raise ValueError("native input backend requires --execute")
    if args.train_every is not None and args.train_every <= 0:
        raise ValueError("--train-every must be positive")
    _validate_ack_max_retries(args)
    state = _LoopState()
    try:
        while args.max_steps is None or state.steps < args.max_steps:
            if _stop_requested(args):
                state.interrupted = True
                break
            _run_live_learn_iteration(args, state)
    except KeyboardInterrupt:
        state.interrupted = True
    return LiveLearnSummary(
        steps=state.steps,
        trained=state.trained,
        interrupted=state.interrupted,
        dataset=str(args.dataset),
        model=str(args.model_out) if args.model_out is not None else None,
    )


@dataclass
class _LoopState:
    steps: int = 0
    pending_labeled_steps: int = 0
    episode_labeled_steps: int = 0
    trained: int = 0
    episodes: int = 0
    interrupted: bool = False


@dataclass(frozen=True)
class _ActionResult:
    changed: bool
    after_step: GameStep | None = None


def _run_live_learn_iteration(args: argparse.Namespace, state: _LoopState) -> None:
    target_window = _target_window(args)
    screenshot_path = _iteration_screenshot_path(args, state.steps + 1, target_window)
    coordinate_space: CoordinateSpace = "window_relative" if target_window is not None and not args.capture_fixture else "screen_absolute"
    try:
        step = _step_from_screen(args, screenshot_path, iteration=state.steps + 1)
    except (PerceptionQualityError, ValueError) as error:
        if args.failure_log is None:
            raise
        _append_failure(
            args,
            reason="fail_closed_perception" if isinstance(error, PerceptionQualityError) else "screen_parse_failed",
            action_id=None,
            before_signature=None,
            after_signature=None,
            retry_count=0,
            latency_ms=0,
            controller_error=str(error),
        )
        state.steps += 1
        return
    action_id = _live_learn_action_id(args, step) if _is_gameplay_step(step) else _default_action_id(step)
    label_source = _label_source(args)
    labeled_step = _with_chosen_action(step, action_id, label_source)
    action = plan_action(
        labeled_step,
        action_id,
        dry_run=not args.execute,
        target_window=target_window,
        coordinate_space=coordinate_space,
    )
    will_append_label = _is_gameplay_step(labeled_step) and _should_append_training_label(args)
    if will_append_label and not _preflight_append(args, labeled_step):
        state.steps += 1
        return
    if args.execute and will_append_label and not _uses_transition_ack(args):
        _record_missing_transition_ack(
            args,
            step=step,
            action_id=action_id,
        )
        state.steps += 1
        return
    controller = _input_controller(args) if args.execute else None
    action_result = _apply_and_acknowledge(
        args,
        step=step,
        action=action,
        action_id=action_id,
        controller=controller,
        screenshot_path=screenshot_path,
        target_window=target_window,
    )
    if not action_result.changed:
        state.steps += 1
        return
    state.steps += 1
    if _is_terminal_step(labeled_step):
        labeled_steps = _append_episode_summary(args, state, labeled_step, action_id)
        _train_after_terminal_return(args, state, labeled_steps)
        return
    if not _is_gameplay_step(labeled_step):
        return
    if not _should_append_training_label(args):
        return
    append_game_step(args.dataset, labeled_step)
    if args.trajectory_out is not None and action_result.after_step is not None:
        _append_trajectory_step(args.trajectory_out, labeled_step, action_result.after_step, action_id, state.steps)
    if _is_supervised_label(labeled_step):
        state.pending_labeled_steps += 1
    state.episode_labeled_steps += 1
    _train_if_due(args, state)


def _iteration_screenshot_path(args: argparse.Namespace, iteration: int, target_window: TargetWindow | None) -> Path:
    if args.capture_fixture is not None:
        return args.capture_fixture
    screenshot_out = args.screenshot_out
    safe_path = screenshot_out.with_name(f"{screenshot_out.stem}-{iteration:06d}{screenshot_out.suffix}")
    if target_window is None:
        return capture_screen(safe_path)
    return capture_screen(safe_path, bbox=target_window.bounds.to_bbox())


def _step_from_screen(args: argparse.Namespace, screenshot_path: Path, *, iteration: int = 1) -> GameStep:
    parsed = parse_ocr_screen(
        screenshot_path,
        _ocr_provider(args, iteration=iteration),
        calibration=load_region_calibration(args.region_calibration) if args.region_calibration is not None else None,
    )
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


def _live_learn_action_id(args: argparse.Namespace, step: GameStep) -> str:
    if args.choice is not None:
        action_id = _resolve_action_id(step, args.choice)
    elif getattr(args, "policy", None) == "first-legal":
        action_id = _default_action_id(step)
    else:
        result = recommend(load_model(args.model), step)
        action_id = result.best.action_id
    _resolve_action_id(step, action_id)
    return action_id


def _label_source(args: argparse.Namespace) -> str:
    if args.choice is not None:
        return "human"
    if getattr(args, "policy", None) is not None:
        return "heuristic"
    return "model_self"


def _default_action_id(step: GameStep) -> str:
    legal_actions = [action for action in step.actions if action.legal]
    if not legal_actions:
        raise ValueError("screen has no legal action candidates")
    return legal_actions[0].identity


def _with_chosen_action(step: GameStep, action_id: str, label_source: str) -> GameStep:
    return GameStep(
        state=step.state,
        actions=step.actions,
        chosen_action_id=action_id,
        outcome=step.outcome,
        observation=step.observation,
        screenshot_path=step.screenshot_path,
        label_source=label_source,
    )


def _is_gameplay_step(step: GameStep) -> bool:
    return step.state.decision_context in GAMEPLAY_CONTEXTS


def _is_terminal_step(step: GameStep) -> bool:
    return step.outcome is not None and step.outcome.terminal


def _should_append_training_label(args: argparse.Namespace) -> bool:
    return (
        args.choice is not None
        or getattr(args, "policy", None) is not None
        or bool(getattr(args, "allow_model_self_labels", False))
    )


def _is_supervised_label(step: GameStep) -> bool:
    return step.label_source in {"human", "search", "heuristic"}


def _stop_requested(args: argparse.Namespace) -> bool:
    stop_file = getattr(args, "stop_file", None)
    return bool(stop_file is not None and stop_file.exists())


def _append_episode_summary(args: argparse.Namespace, state: _LoopState, step: GameStep, restart_action_id: str) -> int:
    if step.outcome is None:
        return 0
    labeled_steps = state.episode_labeled_steps
    if labeled_steps <= 0:
        return 0
    _propagate_terminal_return(args.dataset, labeled_steps, step.outcome)
    if args.episodes_out is None:
        state.episode_labeled_steps = 0
        return labeled_steps
    state.episodes += 1
    row = {
        "episode": state.episodes,
        "floor_reached": step.outcome.floor_reached,
        "hp_remaining": step.outcome.hp_remaining,
        "restart_action_id": restart_action_id,
        "steps": labeled_steps,
        "victory": step.outcome.victory,
    }
    state.episode_labeled_steps = 0
    args.episodes_out.parent.mkdir(parents=True, exist_ok=True)
    with args.episodes_out.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")
    return labeled_steps


def _propagate_terminal_return(dataset: Path, labeled_steps: int, terminal_outcome: StepOutcome) -> None:
    if labeled_steps <= 0 or not dataset.exists():
        return
    steps = load_game_steps(dataset)
    episode_return = 1.0 if terminal_outcome.victory else 0.0
    propagated = StepOutcome(
        victory=terminal_outcome.victory,
        floor_reached=terminal_outcome.floor_reached,
        hp_remaining=terminal_outcome.hp_remaining,
        immediate_reward=episode_return,
        terminal=False,
    )
    start = max(0, len(steps) - labeled_steps)
    for index in range(start, len(steps)):
        step = steps[index]
        steps[index] = GameStep(
            state=step.state,
            actions=step.actions,
            chosen_action_id=step.chosen_action_id,
            outcome=propagated,
            observation=step.observation,
            screenshot_path=step.screenshot_path,
            label_source=step.label_source,
        )
    write_game_steps(dataset, steps)


def _train_if_due(args: argparse.Namespace, state: _LoopState) -> None:
    if args.train_every is None or args.model_out is None:
        return
    if state.pending_labeled_steps < args.train_every:
        return
    _train_model(args, state)


def _train_after_terminal_return(args: argparse.Namespace, state: _LoopState, labeled_steps: int) -> None:
    if labeled_steps <= 0 or args.train_every is None or args.model_out is None:
        return
    _train_model(args, state)


def _train_model(args: argparse.Namespace, state: _LoopState) -> None:
    model = train_torch_model(
        load_game_steps(args.dataset),
        character=args.character,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
    )
    save_model(model, args.model_out)
    state.pending_labeled_steps = 0
    state.trained += 1


def _apply_and_acknowledge(
    args: argparse.Namespace,
    *,
    step: GameStep,
    action,
    action_id: str,
    controller,
    screenshot_path: Path,
    target_window: TargetWindow | None,
) -> _ActionResult:
    start = time.perf_counter()
    try:
        if not _uses_transition_ack(args):
            apply_action(action, controller)
            return _ActionResult(changed=True)
        final_ack: TransitionAcknowledgement | None = None
        final_after: GameStep | None = None
        retry_count = 0
        deferred_controller = _deferred_input_controller(controller)
        try:
            apply_action(action, deferred_controller)
            for attempt in range(1, args.ack_max_retries + 2):
                ack_step = _ack_poll_step(args, screenshot_path, attempt, target_window)
                final_after = ack_step
                final_ack = acknowledge_transition(step, [] if ack_step is None else [ack_step], action_id)
                retry_count = attempt - 1
                if not final_ack.retry_recommended:
                    break
            _finish_deferred_input(deferred_controller, changed=final_ack is not None and final_ack.status == "changed")
        except Exception:
            _finish_deferred_input(deferred_controller, changed=False)
            raise
        if final_ack is not None and final_ack.status == "changed":
            return _ActionResult(changed=True, after_step=final_after)
        if final_ack is not None:
            _append_failure(
                args,
                reason=final_ack.status,
                action_id=action_id,
                before_signature=final_ack.before_signature,
                after_signature=final_ack.after_signature,
                retry_count=retry_count,
                latency_ms=_latency_ms(start),
                controller_error=None,
            )
        return _ActionResult(changed=False, after_step=final_after)
    except Exception as error:
        before = acknowledge_transition(step, [], action_id)
        _append_failure(
            args,
            reason="controller_error",
            action_id=action_id,
            before_signature=before.before_signature,
            after_signature=None,
            retry_count=0,
            latency_ms=_latency_ms(start),
            controller_error=str(error),
        )
        if args.failure_log is None:
            raise
        return _ActionResult(changed=False)


def _record_missing_transition_ack(
    args: argparse.Namespace,
    *,
    step: GameStep,
    action_id: str,
) -> None:
    start = time.perf_counter()
    before = acknowledge_transition(step, [], action_id)
    _append_failure(
        args,
        reason="missing_transition_ack",
        action_id=action_id,
        before_signature=before.before_signature,
        after_signature=None,
        retry_count=0,
        latency_ms=_latency_ms(start),
        controller_error=None,
    )
    if args.failure_log is None:
        raise ValueError("live-learn-loop --execute requires transition ack for gameplay labels")


def _uses_transition_ack(args: argparse.Namespace) -> bool:
    return bool(args.ack_live_poll or args.ack_ocr_fixture_sequence is not None)


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
    parsed = parse_ocr_screen(
        screenshot_path,
        provider,
        calibration=load_region_calibration(args.region_calibration) if args.region_calibration is not None else None,
    )
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


def _ack_live_poll_step(args: argparse.Namespace, attempt: int, target_window: TargetWindow | None) -> GameStep | None:
    if args.screenshot_out is None:
        return None
    ack_path = args.screenshot_out.with_name(f"{args.screenshot_out.stem}-ack-{attempt:06d}{args.screenshot_out.suffix}")
    if target_window is None:
        screenshot_path = capture_screen(ack_path)
    else:
        screenshot_path = capture_screen(ack_path, bbox=target_window.bounds.to_bbox())
    return _step_from_screen(args, screenshot_path, iteration=attempt)


def _frame_tokens(frame) -> list[OcrToken]:
    return [
        OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
        for row in frame
    ]


def _preflight_append(args: argparse.Namespace, step: GameStep) -> bool:
    try:
        _preflight_jsonl_append(args.dataset)
        if args.trajectory_out is not None:
            _preflight_jsonl_append(args.trajectory_out)
    except OSError as error:
        if args.failure_log is None:
            raise
        before = acknowledge_transition(step, [], step.chosen_action_id or "")
        _append_failure(
            args,
            reason="dataset_preflight_failed",
            action_id=step.chosen_action_id,
            before_signature=before.before_signature,
            after_signature=None,
            retry_count=0,
            latency_ms=0,
            controller_error=str(error),
        )
        return False
    return True


def _preflight_jsonl_append(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"jsonl path is a directory: {path}")
    existed = path.exists()
    with path.open("a", encoding="utf-8"):
        pass
    if not existed:
        path.unlink()


def _append_trajectory_step(
    trajectory_out: Path,
    before: GameStep,
    after: GameStep,
    action_id: str,
    turn_index: int,
) -> None:
    selected = next(action for action in before.actions if action.identity == action_id)
    trajectory = TrajectoryStep(
        run_id="live-learn-loop",
        seed=0,
        game_version=before.state.game_version,
        floor=before.state.floor,
        room_type=before.state.decision_context,
        turn_index=turn_index,
        state_before=_episode_state(before, turn_index),
        legal_actions=[action for action in before.actions if action.legal],
        selected_action=selected,
        state_after=_episode_state(after, turn_index + 1),
        reward=_trajectory_reward(after),
        terminal=False if after.outcome is None else after.outcome.terminal,
        label_source=before.label_source,
    )
    trajectory_out.parent.mkdir(parents=True, exist_ok=True)
    with trajectory_out.open("a", encoding="utf-8") as file:
        file.write(trajectory.to_json() + "\n")


def _trajectory_reward(after: GameStep) -> float:
    if after.outcome is None:
        return 0.0
    if after.outcome.terminal and after.outcome.victory:
        return 1.0
    if after.outcome.terminal:
        return -1.0
    return after.outcome.immediate_reward


def _episode_state(step: GameStep, turn_index: int) -> EpisodeState:
    return EpisodeState(
        run_id="live-learn-loop",
        seed=0,
        game_version=step.state.game_version,
        floor=step.state.floor,
        room_type=step.state.decision_context,
        turn_index=turn_index,
    )


def _append_failure(
    args: argparse.Namespace,
    *,
    reason: str,
    action_id: str | None,
    before_signature: str | None,
    after_signature: str | None,
    retry_count: int,
    latency_ms: int,
    controller_error: str | None,
) -> None:
    if args.failure_log is None:
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
    args.failure_log.parent.mkdir(parents=True, exist_ok=True)
    with args.failure_log.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _validate_ack_max_retries(args: argparse.Namespace) -> None:
    if getattr(args, "ack_max_retries", 0) < 0:
        raise ValueError("--ack-max-retries must be non-negative")


def _input_controller(args: argparse.Namespace) -> JsonlInputController | NativeInputController:
    if args.input_backend == "native":
        return NativeInputController()
    return JsonlInputController(args.input_log)


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


def _target_window(args: argparse.Namespace) -> TargetWindow | None:
    if args.target_process is None:
        return None
    return WindowDetector().detect(args.target_process)


def _resolve_action_id(step: GameStep, choice: str) -> str:
    try:
        return resolve_action_identity(step.actions, choice)
    except ValueError as error:
        if "not present" in str(error):
            raise ValueError(f"chosen action is not present in legal action candidates: {choice}") from error
        raise


def _captured_state(args: argparse.Namespace) -> Any:
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


def _split_csv(value: str) -> list[str]:
    return [item for item in value.split(",") if item]


def _ocr_provider(args: argparse.Namespace, *, iteration: int = 1) -> OcrProvider:
    if args.ocr_provider == "tesseract":
        kwargs = (
            {"language": args.ocr_language, "tessdata_dir": args.tessdata_dir}
            | ({"binary": args.tesseract_binary} if args.tesseract_binary != "tesseract" else {})
            | ({"page_segmentation_mode": args.ocr_psm} if args.ocr_psm is not None else {})
        )
        return TesseractOcrProvider(**kwargs)
    if args.ocr_fixture_sequence is not None:
        return FakeOcrProvider(_ocr_sequence_tokens(args.ocr_fixture_sequence, iteration))
    if args.ocr_fixture is None:
        raise ValueError("ocr fixture is required for fixture OCR provider")
    return FakeOcrProvider(
        [
            OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
            for row in load_json_file(args.ocr_fixture)
        ]
    )


def _ocr_sequence_tokens(path: Path, iteration: int) -> list[OcrToken]:
    frames = load_json_file(path)
    if not frames:
        raise ValueError("ocr fixture sequence must contain at least one frame")
    frame = frames[min(iteration - 1, len(frames) - 1)]
    return [
        OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
        for row in frame
    ]
