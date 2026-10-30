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


_SELF_HP_CARDS = ("HEMOKINESIS", "BLOODLETTING", "OFFERING", "BRUTALITY", "COMBUST")


def pick_action(snapshot: TelemetrySnapshot, policy: QStarPolicy, search_depth: int) -> MacroAction:
    if snapshot.phase == "combat":
        plays = [action for action in snapshot.valid_actions if action.action_type == "play_card"]
        if int(snapshot.player.get("hp", 0)) <= 20:
            plays = [action for action in plays if not _costs_hp(snapshot, action)]
            if not plays:
                end_turn = next((action for action in snapshot.valid_actions if action.action_type == "end_turn"), None)
                if end_turn is not None:
                    return end_turn
        if plays:
            return max(
                plays, key=lambda action: (policy.qstar(snapshot, action, search_depth), _card_score(snapshot, action))
            )
    return policy.select(snapshot, search_depth)


def _costs_hp(snapshot: TelemetrySnapshot, action: MacroAction) -> bool:
    slot = int(action.args.get("hand_slot", 0))
    card = snapshot.hand[slot] if 0 <= slot < len(snapshot.hand) else {}
    return str(card.get("id", "")).upper() in _SELF_HP_CARDS


def _card_score(snapshot: TelemetrySnapshot, action: MacroAction) -> tuple[int, int]:
    slot = int(action.args.get("hand_slot", 0))
    card = snapshot.hand[slot] if 0 <= slot < len(snapshot.hand) else {}
    return int(card.get("damage", 0)), int(card.get("block", 0))


def is_cleared(snapshot: TelemetrySnapshot) -> bool:
    extras = snapshot.extras
    if extras.get("act3_boss_cleared") in (True, 1, "1", "true"):
        return True
    if extras.get("victory") in (True, 1, "1", "true"):
        return True
    return False


def reward_between(previous: TelemetrySnapshot, current: TelemetrySnapshot) -> tuple[float, bool]:
    terminated = current.phase == "terminal" or is_cleared(current)
    if (
        not _same_run(previous, current)
        or previous.extras.get("player_authoritative") is False
        or current.extras.get("player_authoritative") is False
        or previous.phase == "menu"
        or current.phase == "menu"
    ):
        return 0.0, terminated
    reward = 0.0
    if previous.phase == "combat" or current.phase == "combat":
        reward = float(int(current.player["hp"]) - int(previous.player["hp"]))
        same_encounter = (
            previous.phase == "combat"
            and current.phase in {"combat", "terminal"}
            and (previous.seed, previous.act, previous.floor) == (current.seed, current.act, current.floor)
            and (previous.screen_id == current.screen_id or current.phase == "terminal")
        )
        if same_encounter:
            current_enemies = {(enemy.get("id"), enemy.get("slot")): enemy for enemy in current.enemies}
            reward += sum(
                int(enemy.get("hp", 0)) - int(current_enemies[key].get("hp", 0))
                for enemy in previous.enemies
                if (key := (enemy.get("id"), enemy.get("slot"))) in current_enemies
            )
            reward += 0.1 * float(int(current.player.get("block", 0)) - int(previous.player.get("block", 0)))
    elif current.floor > previous.floor:
        reward = 1.0
    return reward, terminated


def _same_run(previous: TelemetrySnapshot, current: TelemetrySnapshot) -> bool:
    return (previous.seed, previous.extras.get("run_instance_id")) == (
        current.seed,
        current.extras.get("run_instance_id"),
    )


def run_live(
    frames: Iterator[TelemetrySnapshot],
    model: Path,
    output: Path,
    send_command: Callable[[MacroAction, str, str], None] | None = None,
    search_depth: int = DEFAULT_SEARCH_DEPTH,
    max_steps: int = DEFAULT_MAX_STEPS,
    until_clear: bool = False,
    command_delay_s: float = 0.0,
    command_cooldown_s: float = 0.0,
) -> dict[str, Any]:
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    policy = QStarPolicy.load_or_create(model)
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
        if previous is not None and not _same_run(previous, snapshot):
            previous = None
            chosen = None
            last_key = None
            last_cmd = 0.0
        if snapshot.phase == "menu" or snapshot.extras.get("loading") or snapshot.screen_id == "loading":
            _write_status(status_path, snapshot, None, commands, waiting=True)
            continue
        if previous is not None and chosen is not None:
            reward, terminated = reward_between(previous, snapshot)
            if (
                previous.extras.get("player_authoritative") is not False
                and snapshot.extras.get("player_authoritative") is not False
                and (previous.phase == "combat" or snapshot.phase == "combat" or snapshot.phase == "terminal")
            ):
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
            chosen = None
            if not until_clear or transitions % 25 == 0:
                policy.save(model)
        if is_cleared(snapshot):
            cleared = True
            _write_status(status_path, snapshot, None, commands, waiting=False)
            break
        if (snapshot.phase == "terminal" and not until_clear) or transitions >= max_steps:
            _write_status(status_path, snapshot, None, commands, waiting=False)
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
            observed_run = snapshot.extras.get("run_instance_id")
            run_id = observed_run if isinstance(observed_run, str) and observed_run.strip() else snapshot.seed
            send_command(chosen, snapshot.screen_id, run_id)
            commands += 1
            _write_status(status_path, snapshot, chosen, commands, waiting=False)
            if command_delay_s > 0:
                time.sleep(command_delay_s)
        else:
            chosen = None
            _write_status(status_path, snapshot, None, commands, waiting=False)
        previous = snapshot
    if transitions or previous is not None:
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


def command_sender(writer: TextIO, execute: bool) -> Callable[[MacroAction, str, str], None] | None:
    if not execute:
        return None

    def send(action: MacroAction, expected_screen_id: str, run_id: str) -> None:
        payload = MacroActionCommand(run_id, action, expected_screen_id).to_dict()
        writer.write(json.dumps(payload, sort_keys=True) + "\n")
        writer.flush()

    return send


def _connect_tcp(address: str, timeout_s: float) -> tuple[TextIO, TextIO]:
    host, port_text = address.rsplit(":", 1)
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    sock = socket.create_connection((host, int(port_text)), timeout=timeout_s)
    reader = None
    try:
        sock.settimeout(None)
        reader = sock.makefile("r", encoding="utf-8", newline="\n")
        writer = sock.makefile("w", encoding="utf-8", newline="\n")
        return reader, writer
    except BaseException:
        if reader is not None:
            reader.close()
        raise
    finally:
        sock.close()


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
    path.parent.mkdir(parents=True, exist_ok=True)
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
