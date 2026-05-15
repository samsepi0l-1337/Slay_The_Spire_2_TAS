from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar


class ValidationError(ValueError):
    """Raised when telemetry or action data is not safe to use."""


def _require(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValidationError(f"missing required field: {key}")
    return mapping[key]


def _require_dict(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = _require(mapping, key)
    if not isinstance(value, dict):
        raise ValidationError(f"{key} must be an object")
    return value


def _require_list(mapping: dict[str, Any], key: str) -> list[Any]:
    value = _require(mapping, key)
    if not isinstance(value, list):
        raise ValidationError(f"{key} must be a list")
    return value


@dataclass(frozen=True)
class MacroAction:
    action_type: str
    args: dict[str, Any]

    allowed_types: ClassVar[set[str]] = {
        "play_card",
        "end_turn",
        "choose_reward",
        "choose_map_node",
        "choose_event_option",
        "shop_buy",
        "shop_remove",
    }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroAction":
        action_type = _require(data, "action_type")
        args = data.get("args", {})
        if action_type not in cls.allowed_types:
            raise ValidationError(f"unknown action_type: {action_type}")
        if not isinstance(args, dict):
            raise ValidationError("args must be an object")
        cls._validate_args(action_type, args)
        return cls(action_type, dict(args))

    @staticmethod
    def _validate_args(action_type: str, args: dict[str, Any]) -> None:
        required: dict[str, tuple[str, ...]] = {
            "play_card": ("hand_slot",),
            "end_turn": (),
            "choose_reward": ("choice_slot",),
            "choose_map_node": ("node_slot",),
            "choose_event_option": ("choice_slot",),
            "shop_buy": ("item_slot",),
            "shop_remove": ("card_slot",),
        }
        for key in required[action_type]:
            if key not in args:
                raise ValidationError(f"{action_type} missing {key}")
        for key, value in args.items():
            if not isinstance(value, int):
                raise ValidationError(f"{key} must be an integer")
            if value < 0:
                raise ValidationError(f"{key} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {"action_type": self.action_type, "args": dict(self.args)}

    @property
    def identity(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


ValidAction = MacroAction


@dataclass(frozen=True)
class TelemetrySnapshot:
    game_version: str
    mod_version: str
    schema_version: int
    seed: str
    timestamp: float
    phase: str
    floor: int
    act: int
    screen_id: str
    player: dict[str, Any]
    hand: list[dict[str, Any]]
    draw_pile: list[dict[str, Any]]
    discard_pile: list[dict[str, Any]]
    exhaust_pile: list[dict[str, Any]]
    enemies: list[dict[str, Any]]
    relics: list[dict[str, Any]]
    potions: list[dict[str, Any]]
    map_choices: list[dict[str, Any]]
    reward_choices: list[dict[str, Any]]
    shop_choices: list[dict[str, Any]]
    event_choices: list[dict[str, Any]]
    rest_choices: list[dict[str, Any]]
    valid_actions: list[MacroAction]
    extras: dict[str, Any]

    phases: ClassVar[set[str]] = {
        "combat",
        "card_reward",
        "map",
        "shop",
        "event",
        "rest",
        "terminal",
        "menu",
    }

    @classmethod
    def from_json(cls, text: str) -> "TelemetrySnapshot":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid json: {exc.msg}") from exc
        if not isinstance(data, dict):
            raise ValidationError("snapshot must be an object")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetrySnapshot":
        phase = _require(data, "phase")
        if phase not in cls.phases:
            raise ValidationError(f"unknown phase: {phase}")
        player = _require_dict(data, "player")
        cls._validate_player(player)
        actions = [MacroAction.from_dict(item) for item in _require_list(data, "valid_actions")]
        identities = [action.identity for action in actions]
        if len(set(identities)) != len(identities):
            raise ValidationError("duplicate valid action identity")
        if not actions and phase not in {"terminal", "menu"}:
            raise ValidationError("valid_actions cannot be empty")
        return cls(
            game_version=str(_require(data, "game_version")),
            mod_version=str(_require(data, "mod_version")),
            schema_version=int(_require(data, "schema_version")),
            seed=str(_require(data, "seed")),
            timestamp=float(_require(data, "timestamp")),
            phase=phase,
            floor=int(_require(data, "floor")),
            act=int(_require(data, "act")),
            screen_id=str(_require(data, "screen_id")),
            player=dict(player),
            hand=list(_require_list(data, "hand")),
            draw_pile=list(_require_list(data, "draw_pile")),
            discard_pile=list(_require_list(data, "discard_pile")),
            exhaust_pile=list(_require_list(data, "exhaust_pile")),
            enemies=list(_require_list(data, "enemies")),
            relics=list(_require_list(data, "relics")),
            potions=list(_require_list(data, "potions")),
            map_choices=list(_require_list(data, "map_choices")),
            reward_choices=list(_require_list(data, "reward_choices")),
            shop_choices=list(_require_list(data, "shop_choices")),
            event_choices=list(_require_list(data, "event_choices")),
            rest_choices=list(_require_list(data, "rest_choices")),
            valid_actions=actions,
            extras=dict(data.get("extras", {})),
        )

    @staticmethod
    def _validate_player(player: dict[str, Any]) -> None:
        for key in ("hp", "max_hp", "energy", "block", "gold"):
            if key not in player:
                raise ValidationError(f"player missing {key}")
            if not isinstance(player[key], int):
                raise ValidationError(f"player.{key} must be an integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_version": self.game_version,
            "mod_version": self.mod_version,
            "schema_version": self.schema_version,
            "seed": self.seed,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "floor": self.floor,
            "act": self.act,
            "screen_id": self.screen_id,
            "player": dict(self.player),
            "hand": list(self.hand),
            "draw_pile": list(self.draw_pile),
            "discard_pile": list(self.discard_pile),
            "exhaust_pile": list(self.exhaust_pile),
            "enemies": list(self.enemies),
            "relics": list(self.relics),
            "potions": list(self.potions),
            "map_choices": list(self.map_choices),
            "reward_choices": list(self.reward_choices),
            "shop_choices": list(self.shop_choices),
            "event_choices": list(self.event_choices),
            "rest_choices": list(self.rest_choices),
            "valid_actions": [action.to_dict() for action in self.valid_actions],
            "extras": dict(self.extras),
        }


@dataclass(frozen=True)
class MacroActionCommand:
    run_id: str
    action: MacroAction
    expected_screen_id: str
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "expected_screen_id": self.expected_screen_id,
            "action": self.action.to_dict(),
        }


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    snapshot: TelemetrySnapshot
    chosen_action: MacroAction
    reward: float
    terminal: bool
    result: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state_json": self.snapshot.to_dict(),
            "valid_actions_json": [action.to_dict() for action in self.snapshot.valid_actions],
            "chosen_action_json": self.chosen_action.to_dict(),
            "reward": self.reward,
            "terminal": self.terminal,
            "result": self.result,
        }
