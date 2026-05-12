from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schema import AutomationAction, DecisionChoice, DecisionSnapshot


@dataclass(frozen=True)
class JsonlInputController:
    log_path: Path

    def send(self, action: AutomationAction) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(action.to_event(), sort_keys=True) + "\n")


def plan_action(snapshot: DecisionSnapshot, choice: DecisionChoice, *, dry_run: bool) -> AutomationAction:
    if choice.action == "pick":
        option_ids = {option.id for option in snapshot.options}
        if choice.option_id not in option_ids:
            raise ValueError(f"choice option_id is not present in snapshot options: {choice.option_id}")
    if choice.action == "skip" and not any(option.kind == "skip" for option in snapshot.options):
        raise ValueError("skip choice requires a skip option in the snapshot")
    return AutomationAction(action=choice.action, option_id=choice.option_id, dry_run=dry_run)


def apply_action(action: AutomationAction, controller: JsonlInputController | None) -> dict[str, bool | str | None]:
    if action.dry_run:
        return action.to_report()
    if controller is None:
        raise ValueError("execute mode requires an input controller")
    controller.send(action)
    return action.to_report()
