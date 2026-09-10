from __future__ import annotations

from copy import deepcopy
from typing import Any

from sts2_tas.action_space import ActionSpace
from sts2_tas.dataset import JsonlTransitionWriter, TransitionRecord
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


class Sts2Env:
    metadata = {"render_modes": []}

    def __init__(
        self,
        snapshot: TelemetrySnapshot,
        writer: JsonlTransitionWriter | None = None,
        policy_id: str | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.action_space = ActionSpace.from_snapshot(snapshot)
        self.writer = writer
        self.policy_id = policy_id
        self.last_seed: int | None = None

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        del options
        self.last_seed = seed
        return self._observe(self.snapshot), {"seed": seed, "valid_action_mask": self.action_masks()}

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        try:
            macro = self.action_space.action_at(action)
        except ValueError as exc:
            raise ValueError(f"illegal action: {action}") from exc
        next_state, reward, terminated = self._apply(macro)
        previous = self.snapshot
        self.snapshot = next_state
        self.action_space = ActionSpace.from_snapshot(next_state)
        info = {"chosen_action": macro.to_dict(), "valid_action_mask": self.action_masks()}
        if self.writer is not None:
            self.writer.append(
                TransitionRecord(
                    game_version=previous.game_version,
                    mod_version=previous.mod_version,
                    seed=previous.seed,
                    timestamp=previous.timestamp,
                    floor=previous.floor,
                    phase=previous.phase,
                    state_json=previous.to_dict(),
                    valid_actions_json=[candidate.to_dict() for candidate in previous.valid_actions],
                    chosen_action_json=macro.to_dict(),
                    reward=reward,
                    terminal=terminated,
                    result="applied",
                    policy_id=self.policy_id,
                )
            )
        return self._observe(next_state), reward, terminated, False, info

    def action_masks(self) -> list[bool]:
        return self.action_space.mask()

    def _apply(self, action: MacroAction) -> tuple[TelemetrySnapshot, float, bool]:
        data = self.snapshot.to_dict()
        if action.action_type == "play_card":
            reward = self._apply_card(data, action)
            if self._enemy_hp_total(data) == 0:
                return self._terminal_snapshot(data), reward, True
            self._rebuild_combat_actions(data)
            return TelemetrySnapshot.from_dict(data), reward, False
        if action.action_type == "end_turn":
            self._end_turn(data)
            self._rebuild_combat_actions(data)
            return TelemetrySnapshot.from_dict(data), 0.0, False
        self._advance_choice_screen(data, action)
        return self._terminal_snapshot(data), 0.0, True

    def _apply_card(self, data: dict[str, Any], action: MacroAction) -> float:
        hand_slot = action.args["hand_slot"]
        target_slot = action.args.get("target_slot", 0)
        hand = data["hand"]
        enemies = data["enemies"]
        if hand_slot >= len(hand):
            raise ValueError("illegal action: hand_slot")
        if target_slot >= len(enemies):
            raise ValueError("illegal action: target_slot")
        card = hand.pop(hand_slot)
        data["discard_pile"].append(card)
        damage = int(card.get("damage", 0))
        block = int(card.get("block", 0))
        data["player"]["energy"] = max(0, int(data["player"]["energy"]) - int(card.get("cost", 0)))
        data["player"]["block"] = int(data["player"]["block"]) + block
        enemy = deepcopy(enemies[target_slot])
        before = int(enemy.get("hp", 0))
        before_block = int(enemy.get("block", 0))
        remaining_block = max(0, before_block - damage)
        hp_damage = max(0, damage - before_block)
        enemy["block"] = remaining_block
        enemy["hp"] = max(0, before - hp_damage)
        enemies[target_slot] = enemy
        return float(before - enemy["hp"] + block * 0.1)

    @staticmethod
    def _advance_choice_screen(data: dict[str, Any], action: MacroAction) -> None:
        choice_fields = {
            "choose_reward": ("reward_choices", "choice_slot"),
            "choose_map_node": ("map_choices", "node_slot"),
            "choose_event_option": ("event_choices", "choice_slot"),
            "shop_buy": ("shop_choices", "item_slot"),
            "shop_remove": ("hand", "card_slot"),
        }
        field, slot_key = choice_fields[action.action_type]
        slot = action.args[slot_key]
        if slot >= len(data[field]):
            raise ValueError(f"illegal action: {slot_key}")
        del data[field][slot]

    @staticmethod
    def _enemy_hp_total(data: dict[str, Any]) -> int:
        return sum(int(enemy.get("hp", 0)) for enemy in data["enemies"])

    @staticmethod
    def _terminal_snapshot(data: dict[str, Any]) -> TelemetrySnapshot:
        data["phase"] = "terminal"
        data["valid_actions"] = []
        return TelemetrySnapshot.from_dict(data)

    @staticmethod
    def _end_turn(data: dict[str, Any]) -> None:
        data["player"]["energy"] = 3
        data["discard_pile"].extend(data["hand"])
        data["hand"] = []
        Sts2Env._draw(data, 5)

    @staticmethod
    def _draw(data: dict[str, Any], count: int) -> None:
        for _ in range(count):
            if not data["draw_pile"]:
                data["draw_pile"] = list(data["discard_pile"])
                data["discard_pile"] = []
            if not data["draw_pile"]:
                return
            data["hand"].append(data["draw_pile"].pop(0))

    @staticmethod
    def _rebuild_combat_actions(data: dict[str, Any]) -> None:
        energy = int(data["player"]["energy"])
        living = [index for index, enemy in enumerate(data["enemies"]) if int(enemy.get("hp", 0)) > 0]
        actions: list[dict[str, Any]] = []
        for hand_slot, card in enumerate(data["hand"]):
            if int(card.get("cost", 0)) > energy:
                continue
            if Sts2Env._is_targeted(card):
                for target_slot in living:
                    actions.append({"action_type": "play_card", "args": {"hand_slot": hand_slot, "target_slot": target_slot}})
                continue
            actions.append({"action_type": "play_card", "args": {"hand_slot": hand_slot}})
        actions.append({"action_type": "end_turn", "args": {}})
        data["valid_actions"] = actions

    @staticmethod
    def _is_targeted(card: dict[str, Any]) -> bool:
        return card.get("type") == "attack" or "damage" in card

    @staticmethod
    def _observe(snapshot: TelemetrySnapshot) -> dict[str, Any]:
        return {
            "phase": snapshot.phase,
            "floor": snapshot.floor,
            "act": snapshot.act,
            "player_hp": snapshot.player["hp"],
            "energy": snapshot.player["energy"],
            "enemy_hp_total": sum(int(enemy.get("hp", 0)) for enemy in snapshot.enemies),
            "hand_count": len(snapshot.hand),
        }
