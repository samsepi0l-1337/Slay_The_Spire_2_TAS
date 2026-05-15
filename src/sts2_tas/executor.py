from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sts2_tas.telemetry_schema import MacroAction


@dataclass(frozen=True)
class MacroExecutor:
    window_title: str
    execute_enabled: bool = False

    def plan(self, action: MacroAction) -> dict[str, Any]:
        return {
            "window_title": self.window_title,
            "execute": False,
            "action": action.to_dict(),
            "commands": self._commands(action),
        }

    def execute(self, action: MacroAction) -> dict[str, Any]:
        if not self.execute_enabled:
            raise PermissionError("native input requires --execute")
        plan = self.plan(action)
        return {**plan, "execute": True, "result": "acknowledged"}

    @staticmethod
    def _commands(action: MacroAction) -> list[dict[str, Any]]:
        if action.action_type == "play_card":
            return [
                {"kind": "click", "target": "hand", "slot": action.args["hand_slot"]},
                {"kind": "click", "target": "enemy", "slot": action.args.get("target_slot", 0)},
            ]
        if action.action_type == "end_turn":
            return [{"kind": "key", "key": "E"}]
        if action.action_type in {"choose_reward", "choose_event_option"}:
            return [{"kind": "click", "target": action.action_type.removeprefix("choose_"), "slot": action.args["choice_slot"]}]
        if action.action_type == "choose_map_node":
            return [{"kind": "click", "target": "map", "slot": action.args["node_slot"]}]
        if action.action_type == "shop_buy":
            return [{"kind": "click", "target": "shop", "slot": action.args["item_slot"]}]
        return [{"kind": "click", "target": "shop_remove", "slot": action.args["card_slot"]}]
