import json
from pathlib import Path

import pytest

from sts2_tas.live import is_cleared, pick_action, reward_between, run_live, should_command
from sts2_tas.qstar import QStarPolicy
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def load_snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot.from_json(FIXTURE.read_text())


def test_reward_between_uses_hp_and_block_deltas() -> None:
    previous = load_snapshot()
    data = json.loads(json.dumps(previous.to_dict()))
    data["enemies"][0]["hp"] = 0
    data["player"]["block"] = 5
    data["player"]["hp"] = 68
    data["phase"] = "terminal"
    data["valid_actions"] = []
    current = TelemetrySnapshot.from_dict(data)

    reward, terminated = reward_between(previous, current)

    assert terminated is True
    assert reward == pytest.approx(6.0 + 0.5 - 2.0)


def test_reward_between_event_overlay_is_not_terminal() -> None:
    data = json.loads(json.dumps(load_snapshot().to_dict()))
    data["phase"] = "event"
    data["screen_id"] = "event"
    data["enemies"] = []
    data["player"]["hp"] = 1
    data["event_choices"] = [{"id": "new_run"}]
    data["valid_actions"] = [{"action_type": "choose_event_option", "args": {"choice_slot": 0}}]
    previous = TelemetrySnapshot.from_dict(data)
    later = json.loads(json.dumps(data))
    later["floor"] = 2
    current = TelemetrySnapshot.from_dict(later)

    reward, terminated = reward_between(previous, TelemetrySnapshot.from_dict(data))
    progressed, still_open = reward_between(previous, current)

    assert terminated is False
    assert reward == 0.0
    assert still_open is False
    assert progressed == 1.0


def test_run_live_skips_td_on_event_menu_loop(tmp_path: Path) -> None:
    data = json.loads(json.dumps(load_snapshot().to_dict()))
    data["phase"] = "event"
    data["screen_id"] = "event"
    data["enemies"] = []
    data["player"]["hp"] = 1
    data["event_choices"] = [{"id": "new_run"}]
    data["valid_actions"] = [{"action_type": "choose_event_option", "args": {"choice_slot": 0}}]
    first = TelemetrySnapshot.from_dict(data)
    second = TelemetrySnapshot.from_dict(data)
    model = tmp_path / "qstar.json"

    result = run_live(
        iter([first, second]),
        model,
        tmp_path / "live.jsonl",
        send_command=lambda _action, _screen: None,
        search_depth=0,
        max_steps=8,
        until_clear=True,
    )

    assert result["commands"] == 2
    assert result["updates"] == 0
    status = json.loads((tmp_path / "live.status.json").read_text())
    assert status["n_actions"] == 1
    assert "ts" in status


def test_run_live_updates_qstar_weights_from_real_transitions(tmp_path: Path) -> None:
    first = load_snapshot()
    data = first.to_dict()
    data["enemies"][0]["hp"] = 0
    data["phase"] = "terminal"
    data["valid_actions"] = []
    second = TelemetrySnapshot.from_dict(data)
    sent: list[MacroAction] = []
    model = tmp_path / "qstar.json"
    output = tmp_path / "live.jsonl"

    result = run_live(
        iter([first, second]),
        model,
        output,
        send_command=lambda action, _screen: sent.append(action),
        search_depth=1,
        max_steps=8,
    )

    assert result["algorithm"] == "qstar-live"
    assert result["transitions"] == 1
    assert result["commands"] == 1
    assert sent[0].action_type == "play_card"
    assert json.loads(model.read_text())["updates"] == 1
    record = json.loads(output.read_text())
    assert record["policy_id"] == "qstar"
    assert record["result"] == "live"
    assert record["terminal"] is True


def test_loading_snapshot_is_accepted_as_menu() -> None:
    data = json.loads(json.dumps(load_snapshot().to_dict()))
    data["phase"] = "event"
    data["screen_id"] = "loading"
    data["valid_actions"] = []
    data["extras"] = {"loading": True}
    snapshot = TelemetrySnapshot.from_dict(data)
    assert snapshot.phase == "menu"
    assert snapshot.valid_actions == []


def test_pick_action_plays_highest_damage_card_in_combat() -> None:
    snapshot = load_snapshot()
    action = pick_action(snapshot, QStarPolicy(), search_depth=0)
    assert action.action_type == "play_card"
    assert action.args["hand_slot"] == 0


def test_pick_action_skips_self_hp_cards_when_low_hp() -> None:
    data = json.loads(json.dumps(load_snapshot().to_dict()))
    data["player"]["hp"] = 11
    data["hand"] = [
        {"id": "HEMOKINESIS", "name": "Hemokinesis", "cost": 1, "type": "attack", "damage": 15},
        {"id": "STRIKE_IRONCLAD", "name": "Strike", "cost": 1, "type": "attack", "damage": 6},
    ]
    data["valid_actions"] = [
        {"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 0}},
        {"action_type": "play_card", "args": {"hand_slot": 1, "target_slot": 0}},
        {"action_type": "end_turn", "args": {}},
    ]
    action = pick_action(TelemetrySnapshot.from_dict(data), QStarPolicy(), search_depth=0)
    assert action.action_type == "play_card"
    assert action.args["hand_slot"] == 1


def test_should_command_skips_loading_and_cooldown() -> None:
    snapshot = load_snapshot()
    assert should_command(snapshot) is True
    loading = json.loads(json.dumps(snapshot.to_dict()))
    loading["phase"] = "menu"
    loading["screen_id"] = "loading"
    loading["valid_actions"] = []
    loading["extras"] = {"loading": True}
    assert should_command(TelemetrySnapshot.from_dict(loading)) is False
    key = (snapshot.screen_id, snapshot.phase, snapshot.act, snapshot.floor)
    assert should_command(snapshot, last_key=key, last_time=100.0, now=100.5, cooldown_s=2.0) is False
    assert should_command(snapshot, last_key=key, last_time=100.0, now=103.0, cooldown_s=2.0) is True


def test_is_cleared_detects_act3_boss_victory() -> None:
    combat = load_snapshot()
    assert is_cleared(combat) is False
    victory = json.loads(json.dumps(combat.to_dict()))
    victory["phase"] = "terminal"
    victory["valid_actions"] = []
    victory["act"] = 3
    victory["extras"] = {"victory": True, "reached_act3": True}
    assert is_cleared(TelemetrySnapshot.from_dict(victory)) is True
    boss = json.loads(json.dumps(combat.to_dict()))
    boss["phase"] = "terminal"
    boss["valid_actions"] = []
    boss["act"] = 3
    boss["extras"] = {"act3_boss_cleared": True}
    assert is_cleared(TelemetrySnapshot.from_dict(boss)) is True
    act3 = json.loads(json.dumps(combat.to_dict()))
    act3["act"] = 3
    act3["phase"] = "terminal"
    act3["valid_actions"] = []
    act3["extras"] = {"reached_act3": True}
    assert is_cleared(TelemetrySnapshot.from_dict(act3)) is False


def test_run_live_until_clear_skips_early_terminal(tmp_path: Path) -> None:
    first = load_snapshot()
    loading = json.loads(json.dumps(first.to_dict()))
    loading["phase"] = "menu"
    loading["screen_id"] = "loading"
    loading["valid_actions"] = []
    loading["extras"] = {"loading": True}
    early = json.loads(json.dumps(first.to_dict()))
    early["phase"] = "terminal"
    early["valid_actions"] = []
    menu = json.loads(json.dumps(first.to_dict()))
    menu["phase"] = "event"
    menu["event_choices"] = [{"id": "new_run"}]
    menu["valid_actions"] = [{"action_type": "choose_event_option", "args": {"choice_slot": 0}}]
    done = json.loads(json.dumps(first.to_dict()))
    done["phase"] = "terminal"
    done["act"] = 3
    done["valid_actions"] = []
    done["extras"] = {"act3_boss_cleared": True, "victory": True}
    stale = tmp_path / "live.jsonl"
    stale.write_text("{}\n")
    result = run_live(
        iter(
            [
                TelemetrySnapshot.from_dict(loading),
                first,
                TelemetrySnapshot.from_dict(early),
                TelemetrySnapshot.from_dict(menu),
                TelemetrySnapshot.from_dict(done),
            ]
        ),
        tmp_path / "qstar.json",
        stale,
        search_depth=0,
        max_steps=20,
        until_clear=True,
        command_delay_s=0.001,
        send_command=lambda _action, _screen: None,
    )
    assert result["cleared"] is True
    assert result["until_clear"] is True
    assert result["transitions"] >= 2


def test_run_live_stops_at_max_steps(tmp_path: Path) -> None:
    first = load_snapshot()
    mid = load_snapshot()
    last = load_snapshot()
    result = run_live(
        iter([first, mid, last]),
        tmp_path / "qstar.json",
        tmp_path / "live.jsonl",
        search_depth=0,
        max_steps=1,
        send_command=lambda _action, _screen: None,
    )
    assert result["transitions"] == 1


def test_patch_points_config_is_fail_closed() -> None:
    config = json.loads((Path(__file__).parents[1] / "config" / "patch-points.v0.107.1.json").read_text())
    assert config["fail_closed"] is True
    assert config["game_version"] == "v0.107.1"
    assert "play_card_action" in config["symbols"]


def test_run_live_skips_empty_masks_and_saves_after_single_frame(tmp_path: Path) -> None:
    empty = TelemetrySnapshot.from_dict({**load_snapshot().to_dict(), "phase": "menu", "valid_actions": []})
    combat = load_snapshot()
    model = tmp_path / "qstar.json"

    skipped = run_live(iter([empty]), model, tmp_path / "empty.jsonl", search_depth=0, max_steps=4)
    planned = run_live(iter([combat]), model, tmp_path / "one.jsonl", search_depth=0, max_steps=4)

    assert skipped["transitions"] == 0
    assert skipped["commands"] == 0
    assert planned["transitions"] == 0
    assert planned["commands"] == 0
    assert model.exists()
