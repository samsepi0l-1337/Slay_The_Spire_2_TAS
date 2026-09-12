from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO

from sts2_tas.dataset import JsonlTransitionWriter, TransitionRecord
from sts2_tas.qstar import DEFAULT_MAX_STEPS, DEFAULT_SEARCH_DEPTH, QStarPolicy
from sts2_tas.telemetry_client import TelemetryFrameReader
from sts2_tas.telemetry_schema import MacroAction, MacroActionCommand, TelemetrySnapshot, ValidationError

DEFAULT_PIPE = "sts2-tas"


def should_command(
    snapshot: TelemetrySnapshot,
    last_key: tuple[str, str, int, int] | None = None,
    last_time: float = 0.0,
    now: float | None = None,
    cooldown_s: float = 0.0,
) -> bool:
    if snapshot.extras.get("loading") or snapshot.screen_id == "loading":
        return False
    if not snapshot.valid_actions:
        return False
    key = (snapshot.screen_id, snapshot.phase, snapshot.act, snapshot.floor)
    clock = time.time() if now is None else now
    if cooldown_s > 0 and last_key == key and clock - last_time < cooldown_s:
        return False
    return True


def pick_action(snapshot: TelemetrySnapshot, policy: QStarPolicy, search_depth: int) -> MacroAction:
    if snapshot.phase == "combat":
        plays = [action for action in snapshot.valid_actions if action.action_type == "play_card"]
        if plays:
            return max(plays, key=lambda action: (policy.qstar(snapshot, action, search_depth), _card_score(snapshot, action)))
    return policy.select(snapshot, search_depth)


def _card_score(snapshot: TelemetrySnapshot, action: MacroAction) -> tuple[int, int]:
    slot = int(action.args.get("hand_slot", 0))
    card = snapshot.hand[slot] if 0 <= slot < len(snapshot.hand) else {}
    return int(card.get("damage", 0)), int(card.get("block", 0))


def is_cleared(snapshot: TelemetrySnapshot) -> bool:
    extras = snapshot.extras
    if extras.get("act3_boss_cleared") in {True, 1, "1", "true"}:
        return True
    if extras.get("victory") in {True, 1, "1", "true"}:
        return True
    return snapshot.act >= 3 and snapshot.phase == "terminal" and bool(extras.get("reached_act3"))


def reward_between(previous: TelemetrySnapshot, current: TelemetrySnapshot) -> tuple[float, bool]:
    previous_hp = _enemy_hp(previous)
    current_hp = _enemy_hp(current)
    reward = 0.0
    if previous.phase == "combat" or current.phase == "combat":
        reward = float(previous_hp - current_hp)
        reward += 0.1 * float(int(current.player.get("block", 0)) - int(previous.player.get("block", 0)))
        reward += float(int(current.player["hp"]) - int(previous.player["hp"]))
    elif current.floor > previous.floor:
        reward = 1.0
    terminated = current.phase == "terminal" or is_cleared(current)
    return reward, terminated


def run_live(
    frames: Iterator[TelemetrySnapshot],
    model: Path,
    output: Path,
    send_command: Callable[[MacroAction], None] | None = None,
    search_depth: int = DEFAULT_SEARCH_DEPTH,
    max_steps: int = DEFAULT_MAX_STEPS,
    until_clear: bool = False,
    command_delay_s: float = 0.0,
    command_cooldown_s: float = 0.0,
) -> dict[str, Any]:
    policy = QStarPolicy.load_or_create(model)
    if until_clear and output.exists():
        output.unlink()
    writer = JsonlTransitionWriter(output)
    status_path = output.with_suffix(".status.json")
    previous: TelemetrySnapshot | None = None
    chosen: MacroAction | None = None
    transitions = 0
    commands = 0
    cleared = False
    last_key: tuple[str, str, int, int] | None = None
    last_cmd = 0.0
    for snapshot in frames:
        if previous is not None and chosen is not None:
            reward, terminated = reward_between(previous, snapshot)
            if previous.phase == "combat" or snapshot.phase == "combat" or snapshot.phase == "terminal":
                policy.update(previous, chosen, reward, snapshot, terminated)
            if not until_clear or transitions % 25 == 0:
                writer.append(
                    TransitionRecord(
                        game_version=previous.game_version,
                        mod_version=previous.mod_version,
                        seed=previous.seed,
                        timestamp=previous.timestamp,
                        floor=previous.floor,
                        phase=previous.phase,
                        state_json=previous.to_dict(),
                        valid_actions_json=[action.to_dict() for action in previous.valid_actions],
                        chosen_action_json=chosen.to_dict(),
                        reward=reward,
                        terminal=terminated,
                        result="live",
                        policy_id="qstar",
                    )
                )
            transitions += 1
            if not until_clear or transitions % 25 == 0:
                policy.save(model)
            if is_cleared(snapshot):
                cleared = True
                policy.save(model)
                break
            if (terminated and not until_clear) or transitions >= max_steps:
                policy.save(model)
                break
        if not should_command(snapshot, last_key, last_cmd, cooldown_s=command_cooldown_s):
            if not snapshot.valid_actions:
                previous = snapshot
                chosen = None
            _write_status(status_path, snapshot, None, commands, waiting=True)
            continue
        chosen = pick_action(snapshot, policy, search_depth)
        last_key = (snapshot.screen_id, snapshot.phase, snapshot.act, snapshot.floor)
        last_cmd = time.time()
        if send_command is not None:
            send_command(chosen)
            commands += 1
            _write_status(status_path, snapshot, chosen, commands, waiting=False)
            if command_delay_s > 0:
                time.sleep(command_delay_s)
        previous = snapshot
    if previous is not None and chosen is not None and transitions == 0:
        policy.save(model)
    return {
        "algorithm": "qstar-live",
        "transitions": transitions,
        "updates": policy.updates,
        "commands": commands,
        "model": str(model),
        "output": str(output),
        "search_depth": search_depth,
        "cleared": cleared,
        "until_clear": until_clear,
    }


def connect_transport(spec: str, timeout_s: float = 30.0) -> tuple[TextIO, TextIO]:
    if spec.startswith("tcp:"):
        return _connect_tcp(spec[4:], timeout_s)
    if spec.startswith("pipe:"):
        return _connect_pipe(spec[5:], timeout_s)
    raise ValueError(f"unsupported transport: {spec}")


def frame_stream(reader_stream: TextIO) -> Iterator[TelemetrySnapshot]:
    reader = TelemetryFrameReader()
    while True:
        line = reader_stream.readline()
        if line == "":
            return
        if line.strip() == "":
            continue
        try:
            yield reader.accept_json(line).payload
        except ValidationError:
            continue


def command_sender(writer: TextIO, execute: bool) -> Callable[[MacroAction], None] | None:
    if not execute:
        return None

    def send(action: MacroAction) -> None:
        payload = MacroActionCommand("live", action, "live").to_dict()
        writer.write(json.dumps(payload, sort_keys=True) + "\n")
        writer.flush()

    return send


def _connect_tcp(address: str, timeout_s: float) -> tuple[TextIO, TextIO]:
    host, port_text = address.rsplit(":", 1)
    sock = socket.create_connection((host, int(port_text)), timeout=timeout_s)
    sock.settimeout(None)
    return sock.makefile("r", encoding="utf-8", newline="\n"), sock.makefile("w", encoding="utf-8", newline="\n")


def _connect_pipe(
    name: str,
    timeout_s: float,
    platform: str = os.name,
    opener: Callable[..., TextIO] = open,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> tuple[TextIO, TextIO]:
    if platform != "nt":
        raise ValueError("named pipes require Windows")
    path = rf"\\.\pipe\{name}"
    deadline = clock() + timeout_s
    while True:
        try:
            handle = opener(path, "r+", encoding="utf-8", buffering=1)
            return handle, handle
        except OSError:
            if clock() >= deadline:
                raise
            sleeper(0.2)


def _write_status(
    path: Path,
    snapshot: TelemetrySnapshot,
    action: MacroAction | None,
    commands: int,
    waiting: bool,
) -> None:
    path.write_text(
        json.dumps(
            {
                "commands": commands,
                "waiting": waiting,
                "phase": snapshot.phase,
                "screen_id": snapshot.screen_id,
                "floor": snapshot.floor,
                "act": snapshot.act,
                "hp": snapshot.player["hp"],
                "enemies": snapshot.enemies,
                "n_actions": len(snapshot.valid_actions),
                "ts": time.time(),
                "action": None if action is None else action.to_dict(),
                "extras": snapshot.extras,
            },
            sort_keys=True,
        )
    )


def _enemy_hp(snapshot: TelemetrySnapshot) -> int:
    return sum(int(enemy.get("hp", 0)) for enemy in snapshot.enemies)
