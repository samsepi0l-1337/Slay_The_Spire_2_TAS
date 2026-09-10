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
from sts2_tas.telemetry_schema import MacroAction, MacroActionCommand, TelemetrySnapshot

DEFAULT_PIPE = "sts2-tas"


def reward_between(previous: TelemetrySnapshot, current: TelemetrySnapshot) -> tuple[float, bool]:
    previous_hp = _enemy_hp(previous)
    current_hp = _enemy_hp(current)
    reward = float(previous_hp - current_hp)
    reward += 0.1 * float(int(current.player.get("block", 0)) - int(previous.player.get("block", 0)))
    reward += float(int(current.player["hp"]) - int(previous.player["hp"]))
    terminated = current.phase in {"terminal", "menu"} or current_hp == 0
    return reward, terminated


def run_live(
    frames: Iterator[TelemetrySnapshot],
    model: Path,
    output: Path,
    send_command: Callable[[MacroAction], None] | None = None,
    search_depth: int = DEFAULT_SEARCH_DEPTH,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> dict[str, Any]:
    policy = QStarPolicy.load_or_create(model)
    writer = JsonlTransitionWriter(output)
    previous: TelemetrySnapshot | None = None
    chosen: MacroAction | None = None
    transitions = 0
    commands = 0
    for snapshot in frames:
        if previous is not None and chosen is not None:
            reward, terminated = reward_between(previous, snapshot)
            policy.update(previous, chosen, reward, snapshot, terminated)
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
            policy.save(model)
            if terminated or transitions >= max_steps:
                break
        if not snapshot.valid_actions:
            previous = snapshot
            chosen = None
            continue
        chosen = policy.select(snapshot, search_depth)
        if send_command is not None:
            send_command(chosen)
            commands += 1
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
        yield reader.accept_json(line).payload


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


def _enemy_hp(snapshot: TelemetrySnapshot) -> int:
    return sum(int(enemy.get("hp", 0)) for enemy in snapshot.enemies)
