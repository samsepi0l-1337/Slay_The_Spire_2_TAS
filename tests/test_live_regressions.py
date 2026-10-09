import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from sts2_tas.live import run_live, frame_stream, _connect_tcp
from sts2_tas.telemetry_client import TelemetryFrameReader
from sts2_tas.telemetry_schema import TelemetrySnapshot, ValidationError
from io import StringIO


def snapshot(**changes):
    data = json.loads((Path(__file__).parent / "fixtures/telemetry-combat.json").read_text())
    data.update(changes)
    return TelemetrySnapshot.from_dict(data)


def test_cooldown_credits_each_action_once(tmp_path, monkeypatch):
    monkeypatch.setattr("sts2_tas.live.time.time", lambda: 100.0)
    result = run_live(iter([snapshot()] * 4), tmp_path / "model.json", tmp_path / "live.jsonl",
                      search_depth=0, command_cooldown_s=2, send_command=lambda _action, _screen: None)
    assert result["commands"] == 1
    assert result["transitions"] == 1
    assert result["updates"] == 1
    assert len((tmp_path / "live.jsonl").read_text().splitlines()) == 1


def test_loading_does_not_consume_pending_transition(tmp_path):
    initial = snapshot()
    loading = snapshot(phase="menu", screen_id="loading", valid_actions=[], extras={"loading": True})
    final = snapshot(phase="terminal", valid_actions=[])
    final.enemies[0]["hp"] = 0
    result = run_live(iter([initial, loading, final]), tmp_path / "model.json", tmp_path / "live.jsonl", search_depth=0)
    record = json.loads((tmp_path / "live.jsonl").read_text())
    assert result["transitions"] == 1
    assert record["terminal"] is True
    assert record["reward"] == 6.0


def test_nested_waiting_status_and_batched_model_persist_at_eof(tmp_path):
    empty = snapshot(phase="menu", valid_actions=[])
    output = tmp_path / "nested/live.jsonl"
    run_live(iter([empty]), tmp_path / "model.json", output)
    assert output.with_suffix(".status.json").exists()
    model = tmp_path / "model.json"
    result = run_live(iter([snapshot()] * 3), model, output, search_depth=0, until_clear=True)
    assert result["updates"] == 2
    assert json.loads(model.read_text())["updates"] == 2


def test_victory_without_pending_action_is_detected(tmp_path):
    final = snapshot(phase="terminal", valid_actions=[], extras={"victory": True})
    result = run_live(iter([final, snapshot()]), tmp_path / "model.json", tmp_path / "live.jsonl", search_depth=0)
    assert result["cleared"] is True
    assert result["transitions"] == 0


@pytest.mark.parametrize("payload", [None, [], "bad", 42])
def test_nonobject_frame_payload_is_rejected_without_advancing_sequence(payload):
    reader = TelemetryFrameReader()
    with pytest.raises(ValidationError, match="payload must be an object"):
        reader.accept_json(json.dumps({"sequence": 1, "payload": payload}))
    assert reader.accept_json(json.dumps({"sequence": 1, "payload": snapshot().to_dict()})).sequence == 1


def test_frame_stream_skips_nonobject_payload():
    stream = StringIO(json.dumps({"sequence": 1, "payload": None}) + "\n" +
                      json.dumps({"sequence": 2, "payload": snapshot().to_dict()}) + "\n")
    assert len(list(frame_stream(stream))) == 1


def test_tcp_releases_socket_owner_and_partial_reader(monkeypatch):
    sock = Mock()
    reader, writer = Mock(), Mock()
    sock.makefile.side_effect = [reader, writer]
    monkeypatch.setattr("sts2_tas.live.socket.create_connection", lambda *a, **k: sock)
    assert _connect_tcp("localhost:1234", 1) == (reader, writer)
    sock.close.assert_called_once()
    sock.reset_mock()
    sock.makefile.side_effect = [reader, OSError("writer failed")]
    with pytest.raises(OSError, match="writer failed"):
        _connect_tcp("localhost:1234", 1)
    reader.close.assert_called_once()
    sock.close.assert_called_once()


@pytest.mark.parametrize("max_steps", [0, -1])
def test_nonpositive_max_steps_sends_no_commands(tmp_path, max_steps):
    send = Mock()
    with pytest.raises(ValueError, match="max_steps must be positive"):
        run_live(iter([snapshot()]), tmp_path / "model.json", tmp_path / "live.jsonl",
                 max_steps=max_steps, send_command=send)
    send.assert_not_called()


def test_victory_after_pending_action_sets_cleared(tmp_path):
    final = snapshot(phase="terminal", valid_actions=[], extras={"victory": True})
    result = run_live(iter([snapshot(), final]), tmp_path / "model.json", tmp_path / "live.jsonl", search_depth=0)
    assert result["cleared"] is True


def test_command_sender_preserves_current_screen():
    from sts2_tas.live import command_sender
    from sts2_tas.telemetry_schema import MacroAction
    writer = StringIO()
    command_sender(writer, execute=True)(MacroAction("end_turn", {}), "combat-screen-7")
    assert json.loads(writer.getvalue())["expected_screen_id"] == "combat-screen-7"


@pytest.mark.parametrize("extras", [
    {"victory": []}, {"act3_boss_cleared": {}}, {"reached_act3": "false"},
])
def test_malformed_victory_flags_do_not_claim_clear(extras):
    from sts2_tas.live import is_cleared
    assert is_cleared(snapshot(phase="terminal", act=3, valid_actions=[], extras=extras)) is False


@pytest.mark.parametrize("direction", ["enter", "leave", "new_floor", "new_enemy"])
def test_encounter_boundaries_do_not_credit_enemy_spawn_or_disappearance(direction):
    from sts2_tas.live import reward_between
    combat = snapshot()
    other = snapshot(phase="map", map_choices=[{"id": "next"}],
                     valid_actions=[{"action_type": "choose_map_node", "args": {"node_slot": 0}}])
    other.enemies.clear()
    if direction == "enter":
        previous, current = other, combat
    elif direction == "leave":
        previous, current = combat, other
    else:
        previous, current = combat, snapshot()
        current.enemies[0]["hp"] = 1
        if direction == "new_floor":
            current = snapshot(floor=2)
            current.enemies[0]["hp"] = 1
        else:
            current.enemies[0]["id"] = "new-enemy"
    current.player["hp"] = 68
    reward, _ = reward_between(previous, current)
    assert reward == -2.0


def test_missing_enemy_does_not_count_as_observed_damage():
    from sts2_tas.live import reward_between
    current = snapshot(phase="terminal", valid_actions=[])
    current.enemies.clear()
    assert reward_between(snapshot(), current) == (0.0, True)


def test_act3_death_is_not_clear():
    from sts2_tas.live import is_cleared
    dead = snapshot(phase="terminal", act=3, valid_actions=[], extras={"reached_act3": True})
    dead.player["hp"] = 0
    assert is_cleared(dead) is False


def test_low_hp_only_hp_cost_card_ends_turn():
    from sts2_tas.live import pick_action
    from sts2_tas.qstar import QStarPolicy
    current = snapshot(hand=[{"id": "HEMOKINESIS", "damage": 15}], valid_actions=[
        {"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 0}},
        {"action_type": "end_turn", "args": {}},
    ])
    current.player["hp"] = 1
    assert pick_action(current, QStarPolicy(), search_depth=0).action_type == "end_turn"


@pytest.mark.parametrize("reverse", [False, True])
def test_menu_placeholder_hp_does_not_become_reward(reverse):
    from sts2_tas.live import reward_between
    combat = snapshot()
    menu = snapshot(phase="menu", valid_actions=[], enemies=[])
    menu.player["hp"] = 1
    previous, current = (menu, combat) if reverse else (combat, menu)
    assert reward_between(previous, current) == (0.0, False)


def test_menu_overlay_preserves_pending_combat_action(tmp_path):
    menu = snapshot(phase="menu", valid_actions=[], enemies=[])
    menu.player["hp"] = 1
    final = snapshot(phase="terminal", valid_actions=[])
    final.enemies[0]["hp"] = 0
    result = run_live(iter([snapshot(), menu, final]), tmp_path / "model.json", tmp_path / "live.jsonl", search_depth=0)
    record = json.loads((tmp_path / "live.jsonl").read_text())
    assert result["updates"] == 1
    assert record["reward"] == 6
    assert record["terminal"] is True
