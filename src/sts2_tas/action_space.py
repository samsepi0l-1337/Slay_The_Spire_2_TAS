from __future__ import annotations

from dataclasses import dataclass

from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


@dataclass(frozen=True)
class ActionSpace:
    actions: tuple[MacroAction, ...]

    @classmethod
    def from_snapshot(cls, snapshot: TelemetrySnapshot) -> "ActionSpace":
        return cls(tuple(snapshot.valid_actions))

    @property
    def n(self) -> int:
        return len(self.actions)

    def mask(self) -> list[bool]:
        return [True for _ in self.actions]

    def action_at(self, index: int) -> MacroAction:
        if index < 0 or index >= len(self.actions):
            raise ValueError(f"illegal action index: {index}")
        return self.actions[index]

    def index_of(self, action: MacroAction) -> int:
        for index, candidate in enumerate(self.actions):
            if candidate == action:
                return index
        raise ValueError(f"illegal action: {action.identity}")
