from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

OptionKind = Literal["card", "relic", "skip"]
InputAction = Literal["pick", "skip"]
CoordinateSpace = Literal["screen_absolute", "window_relative"]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class WindowBounds:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("window bounds must have positive width and height")

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def to_bbox(self) -> Box:
        return (self.left, self.top, self.right, self.bottom)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class TargetWindow:
    process: str
    title: str
    bounds: WindowBounds

    def __post_init__(self) -> None:
        if not self.process:
            raise ValueError("target window process is required")
        if not self.title:
            raise ValueError("target window title is required")

    def to_dict(self) -> dict[str, Any]:
        return {"process": self.process, "title": self.title, "bounds": self.bounds.to_dict()}


@dataclass(frozen=True)
class OcrResult:
    text: str
    box: Box
    confidence: float


@dataclass(frozen=True)
class RecognizedOption:
    id: str
    name: str
    kind: OptionKind
    box: Box
    confidence: float
    source_text: str
    tags: list[str]


@dataclass(frozen=True)
class ParsedScreen:
    kind: str
    options: list[RecognizedOption]
    screenshot_path: Path
    resolution: tuple[int, int]
    state_payload: dict[str, Any] | None = None
    state_boxes: dict[str, Box] | None = None
    missing_fields: list[str] | None = None
    unknown_tokens: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["screenshot_path"] = str(self.screenshot_path)
        data["state_payload"] = self.state_payload or {}
        data["state_boxes"] = {
            key: list(value)
            for key, value in (self.state_boxes or {}).items()
        }
        data["missing_fields"] = list(self.missing_fields or [])
        data["unknown_tokens"] = list(self.unknown_tokens or [])
        return data


@dataclass(frozen=True)
class AutomationAction:
    action: InputAction
    option_id: str | None
    dry_run: bool
    target: Box | None = None
    targets: list[Box] | None = None
    coordinate_space: CoordinateSpace = "screen_absolute"
    target_window: TargetWindow | None = None

    def __post_init__(self) -> None:
        if self.coordinate_space not in {"screen_absolute", "window_relative"}:
            raise ValueError(f"unsupported coordinate_space: {self.coordinate_space}")
        if self.target_window is not None and self.coordinate_space != "window_relative":
            raise ValueError("target_window input requires window_relative coordinate_space")
        if self.coordinate_space == "window_relative" and self.target_window is None:
            raise ValueError("window_relative actions require target_window metadata")
        if self.targets is not None and not self.targets:
            raise ValueError("target sequence cannot be empty")

    def input_plan(self) -> dict[str, Any]:
        target_boxes = self.targets or ([] if self.target is None else [self.target])
        if not target_boxes:
            if self.action == "pick":
                raise ValueError("pick automation actions require target")
            return {"kind": "keypress", "key": "escape"}
        steps = [_click_step(box, self.coordinate_space, self.target_window) for box in target_boxes]
        if len(steps) > 1:
            return {"kind": "sequence", "steps": steps}
        return steps[0]

    def to_event(self) -> dict[str, Any]:
        event: dict[str, Any] = {"action": self.action, "option_id": self.option_id}
        if self.target is not None:
            event["target"] = list(self.target)
        if self.targets is not None:
            event["targets"] = [list(target) for target in self.targets]
        event["coordinate_space"] = self.coordinate_space
        if self.target_window is not None:
            event["target_window"] = self.target_window.to_dict()
        event["input_plan"] = self.input_plan()
        return event

    def to_report(self) -> dict[str, Any]:
        report = {"dry_run": self.dry_run, **self.to_event()}
        return report


def _click_step(
    target: Box,
    coordinate_space: CoordinateSpace,
    target_window: TargetWindow | None,
) -> dict[str, int | str]:
    left, top, right, bottom = target
    x = (left + right) // 2
    y = (top + bottom) // 2
    if coordinate_space == "window_relative" and target_window is not None:
        x += target_window.bounds.left
        y += target_window.bounds.top
    return {"kind": "click", "x": x, "y": y}


@dataclass(frozen=True)
class RunEpisode:
    seed: int
    steps: int
    choices: list[dict[str, str]]
    victory: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeedEvaluation:
    episodes: int
    victories: int
    win_rate: float
    average_steps: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


from .ml_schema import (  # noqa: E402
    ActionCandidate,
    CardInstance,
    GameStep,
    MonsterState,
    ObservationQuality,
    PathCandidate,
    PlayerState,
    PotionState,
    RelicState,
    StepOutcome,
    StructuredGameState,
)
