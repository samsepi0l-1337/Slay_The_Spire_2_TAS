from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Literal

ChoiceKind = Literal["card", "relic", "skip"]
Action = Literal["pick", "skip"]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class ChoiceOption:
    id: str
    name: str
    kind: ChoiceKind
    tags: list[str]
    box: Box | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("option id is required")
        if not self.name:
            raise ValueError("option name is required")
        if self.kind not in {"card", "relic", "skip"}:
            raise ValueError(f"unsupported option kind: {self.kind}")


@dataclass(frozen=True)
class DecisionChoice:
    action: Action
    option_id: str | None = None

    def __post_init__(self) -> None:
        if self.action not in {"pick", "skip"}:
            raise ValueError(f"unsupported decision action: {self.action}")
        if self.action == "pick" and not self.option_id:
            raise ValueError("pick decisions require option_id")
        if self.action == "skip" and self.option_id is not None:
            raise ValueError("skip decisions must not include option_id")

    def matches(self, option: ChoiceOption) -> bool:
        if self.action == "skip":
            return option.kind == "skip"
        return option.id == self.option_id


@dataclass(frozen=True)
class DecisionSnapshot:
    game_version: str
    branch: str
    character: str
    ascension: int
    floor: int
    deck: list[str]
    relics: list[str]
    hp: int
    gold: int
    options: list[ChoiceOption]
    chosen: DecisionChoice | None
    skipped: bool
    screenshot_path: Path

    def __post_init__(self) -> None:
        if not self.game_version:
            raise ValueError("game_version is required")
        if not self.branch:
            raise ValueError("branch is required")
        if not self.character:
            raise ValueError("character is required")
        if self.ascension < 0:
            raise ValueError("ascension must be non-negative")
        if self.floor < 1:
            raise ValueError("floor must be at least 1")
        if self.hp < 0:
            raise ValueError("hp must be non-negative")
        if self.gold < 0:
            raise ValueError("gold must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["options"] = [_choice_option_to_dict(option) for option in self.options]
        data["screenshot_path"] = str(self.screenshot_path)
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionSnapshot:
        chosen = data.get("chosen")
        return cls(
            game_version=data["game_version"],
            branch=data["branch"],
            character=data["character"],
            ascension=int(data["ascension"]),
            floor=int(data["floor"]),
            deck=list(data["deck"]),
            relics=list(data["relics"]),
            hp=int(data["hp"]),
            gold=int(data["gold"]),
            options=[_choice_option_from_dict(option) for option in data["options"]],
            chosen=DecisionChoice(**chosen) if chosen is not None else None,
            skipped=bool(data["skipped"]),
            screenshot_path=Path(data["screenshot_path"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> DecisionSnapshot:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class OcrResult:
    text: str
    box: Box
    confidence: float


@dataclass(frozen=True)
class RecognizedOption:
    id: str
    name: str
    kind: ChoiceKind
    box: Box
    confidence: float
    source_text: str
    tags: list[str]

    def to_choice_option(self) -> ChoiceOption:
        return ChoiceOption(id=self.id, name=self.name, kind=self.kind, tags=self.tags, box=self.box)


@dataclass(frozen=True)
class ParsedScreen:
    kind: str
    options: list[RecognizedOption]
    screenshot_path: Path
    resolution: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["screenshot_path"] = str(self.screenshot_path)
        return data


@dataclass(frozen=True)
class AutomationAction:
    action: Action
    option_id: str | None
    dry_run: bool
    target: Box | None = None

    def input_plan(self) -> dict[str, int | str]:
        if self.target is None:
            if self.action == "pick":
                raise ValueError("pick automation actions require target")
            return {"kind": "keypress", "key": "escape"}
        left, top, right, bottom = self.target
        return {"kind": "click", "x": (left + right) // 2, "y": (top + bottom) // 2}

    def to_event(self) -> dict[str, Any]:
        event: dict[str, Any] = {"action": self.action, "option_id": self.option_id}
        if self.target is not None:
            event["target"] = list(self.target)
        event["input_plan"] = self.input_plan()
        return event

    def to_report(self) -> dict[str, Any]:
        report = {"dry_run": self.dry_run, **self.to_event()}
        return report


def _choice_option_to_dict(option: ChoiceOption) -> dict[str, Any]:
    data = asdict(option)
    if data["box"] is None:
        del data["box"]
    return data


def _choice_option_from_dict(data: dict[str, Any]) -> ChoiceOption:
    box = data.get("box")
    return ChoiceOption(
        id=data["id"],
        name=data["name"],
        kind=data["kind"],
        tags=list(data["tags"]),
        box=tuple(box) if box is not None else None,  # type: ignore[arg-type]
    )


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
