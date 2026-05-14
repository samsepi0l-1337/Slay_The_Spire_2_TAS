from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .automation import JsonlInputController, NativeInputController, apply_action, plan_action
from .capture_state import load_captured_game_state
from .ml_entities import resolve_action_identity
from .model import load_model, recommend, save_model, train_torch_model
from .recognition import FakeOcrProvider, OcrProvider, OcrToken, TesseractOcrProvider, parse_ocr_screen
from .runtime import capture_screen
from .schema import CoordinateSpace, GameStep, StepOutcome, TargetWindow
from .step_factory import game_step_from_parsed_screen
from .torch_dataset import append_game_step, load_game_steps, write_game_steps
from .windowing import WindowDetector


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
    state = _LoopState()
    try:
        while args.max_steps is None or state.steps < args.max_steps:
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


def _run_live_learn_iteration(args: argparse.Namespace, state: _LoopState) -> None:
    target_window = _target_window(args)
    screenshot_path = _iteration_screenshot_path(args, state.steps + 1, target_window)
    coordinate_space: CoordinateSpace = "window_relative" if target_window is not None and not args.capture_fixture else "screen_absolute"
    step = _step_from_screen(args, screenshot_path, iteration=state.steps + 1)
    action_id = _live_learn_action_id(args, step) if _is_gameplay_step(step) else _default_action_id(step)
    labeled_step = _with_chosen_action(step, action_id)
    action = plan_action(
        labeled_step,
        action_id,
        dry_run=not args.execute,
        target_window=target_window,
        coordinate_space=coordinate_space,
    )
    controller = _input_controller(args) if args.execute else None
    apply_action(action, controller)
    state.steps += 1
    if _is_terminal_step(labeled_step):
        _append_episode_summary(args, state, labeled_step, action_id)
    if not _is_gameplay_step(labeled_step):
        return
    if not _should_append_training_label(args):
        return
    append_game_step(args.dataset, labeled_step)
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
    parsed = parse_ocr_screen(screenshot_path, _ocr_provider(args, iteration=iteration))
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
    else:
        result = recommend(load_model(args.model), step)
        action_id = result.best.action_id
    _resolve_action_id(step, action_id)
    return action_id


def _default_action_id(step: GameStep) -> str:
    legal_actions = [action for action in step.actions if action.legal]
    if not legal_actions:
        raise ValueError("screen has no legal action candidates")
    return legal_actions[0].identity


def _with_chosen_action(step: GameStep, action_id: str) -> GameStep:
    return GameStep(
        state=step.state,
        actions=step.actions,
        chosen_action_id=action_id,
        outcome=step.outcome,
        observation=step.observation,
        screenshot_path=step.screenshot_path,
    )


def _is_gameplay_step(step: GameStep) -> bool:
    return step.state.decision_context in {"card_reward", "relic_choice"}


def _is_terminal_step(step: GameStep) -> bool:
    return step.outcome is not None and step.outcome.terminal


def _should_append_training_label(args: argparse.Namespace) -> bool:
    return args.choice is not None or bool(getattr(args, "allow_model_self_labels", False))


def _append_episode_summary(args: argparse.Namespace, state: _LoopState, step: GameStep, restart_action_id: str) -> None:
    if step.outcome is None:
        return
    _propagate_terminal_return(args.dataset, state.episode_labeled_steps, step.outcome)
    if args.episodes_out is None:
        state.episode_labeled_steps = 0
        return
    state.episodes += 1
    row = {
        "episode": state.episodes,
        "floor_reached": step.outcome.floor_reached,
        "hp_remaining": step.outcome.hp_remaining,
        "restart_action_id": restart_action_id,
        "steps": state.episode_labeled_steps,
        "victory": step.outcome.victory,
    }
    state.episode_labeled_steps = 0
    args.episodes_out.parent.mkdir(parents=True, exist_ok=True)
    with args.episodes_out.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")


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
        )
    write_game_steps(dataset, steps)


def _train_if_due(args: argparse.Namespace, state: _LoopState) -> None:
    if args.train_every is None or args.model_out is None:
        return
    if state.pending_labeled_steps < args.train_every:
        return
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


def _input_controller(args: argparse.Namespace) -> JsonlInputController | NativeInputController:
    if args.input_backend == "native":
        return NativeInputController()
    return JsonlInputController(args.input_log)


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
        return TesseractOcrProvider(language=args.ocr_language)
    if args.ocr_fixture_sequence is not None:
        return FakeOcrProvider(_ocr_sequence_tokens(args.ocr_fixture_sequence, iteration))
    if args.ocr_fixture is None:
        raise ValueError("ocr fixture is required for fixture OCR provider")
    return FakeOcrProvider(
        [
            OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
            for row in json.loads(args.ocr_fixture.read_text(encoding="utf-8"))
        ]
    )


def _ocr_sequence_tokens(path: Path, iteration: int) -> list[OcrToken]:
    frames = json.loads(path.read_text(encoding="utf-8"))
    if not frames:
        raise ValueError("ocr fixture sequence must contain at least one frame")
    frame = frames[min(iteration - 1, len(frames) - 1)]
    return [
        OcrToken(text=row["text"], box=tuple(row["box"]), confidence=float(row["confidence"]))  # type: ignore[arg-type]
        for row in frame
    ]
