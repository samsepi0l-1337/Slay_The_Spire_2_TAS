import json
from io import StringIO
from pathlib import Path

import pytest

from sts2_tas.action_space import ActionSpace
from sts2_tas.dataset import JsonlTransitionWriter, TransitionRecord
from sts2_tas.env import Sts2Env
from sts2_tas.executor import MacroExecutor
from sts2_tas.heuristic import choose_action
from sts2_tas.telemetry_client import TelemetryFrameReader, TelemetryStreamClient
from sts2_tas.telemetry_schema import MacroAction, MacroActionCommand, RunRecord, TelemetrySnapshot, ValidationError


FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def load_snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot.from_json(FIXTURE.read_text())


def test_telemetry_snapshot_rejects_missing_required_field() -> None:
    data = json.loads(FIXTURE.read_text())
    del data["seed"]

    with pytest.raises(ValidationError, match="seed"):
        TelemetrySnapshot.from_dict(data)


def test_action_space_round_trips_and_rejects_duplicate_actions() -> None:
    snapshot = load_snapshot()
    space = ActionSpace.from_snapshot(snapshot)

    action = MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})
    index = space.index_of(action)

    assert space.n == 3
    assert space.action_at(index) == action
    assert space.mask() == [True, True, True]
    with pytest.raises(ValueError, match="illegal action index"):
        space.action_at(-1)
    with pytest.raises(ValueError, match="illegal action"):
        space.index_of(MacroAction("shop_buy", {"item_slot": 0}))

    duplicated = json.loads(FIXTURE.read_text())
    duplicated["valid_actions"].append(duplicated["valid_actions"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        TelemetrySnapshot.from_dict(duplicated)


def test_env_step_applies_legal_macro_action_and_logs_transition(tmp_path: Path) -> None:
    snapshot = load_snapshot()
    writer = JsonlTransitionWriter(tmp_path / "transitions.jsonl")
    env = Sts2Env(snapshot, writer=writer)

    observation, info = env.reset(seed=123)
    result_observation, reward, terminated, truncated, step_info = env.step(0)

    assert observation["phase"] == "combat"
    assert info["seed"] == 123
    assert result_observation["enemy_hp_total"] == 0
    assert reward == 6.0
    assert terminated is True
    assert truncated is False
    assert step_info["chosen_action"]["action_type"] == "play_card"
    assert len((tmp_path / "transitions.jsonl").read_text().splitlines()) == 1


def test_env_rejects_invalid_action_index() -> None:
    env = Sts2Env(load_snapshot())

    with pytest.raises(ValueError, match="illegal action"):
        env.step(99)


def test_executor_dry_run_and_execute_gate() -> None:
    action = MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})
    executor = MacroExecutor(window_title="Slay the Spire 2")

    plan = executor.plan(action)

    assert plan["execute"] is False
    assert plan["commands"][0]["kind"] == "click"
    with pytest.raises(PermissionError, match="--execute"):
        executor.execute(action)

    executed = MacroExecutor("Slay the Spire 2", execute_enabled=True).execute(MacroAction("end_turn", {}))
    assert executed["execute"] is True
    assert executed["result"] == "acknowledged"


def test_heuristic_prefers_lethal_attack_then_end_turn_without_energy() -> None:
    snapshot = load_snapshot()
    assert choose_action(snapshot) == MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})

    data = json.loads(FIXTURE.read_text())
    data["player"]["energy"] = 0
    data["valid_actions"] = [{"action_type": "end_turn", "args": {}}]
    assert choose_action(TelemetrySnapshot.from_dict(data)) == MacroAction("end_turn", {})


def test_heuristic_phase_fallbacks_and_no_action_guard() -> None:
    data = json.loads(FIXTURE.read_text())
    data["enemies"][0]["hp"] = 20
    assert choose_action(TelemetrySnapshot.from_dict(data)) == MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})

    data["valid_actions"] = [
        {"action_type": "choose_reward", "args": {"choice_slot": 1}},
        {"action_type": "end_turn", "args": {}},
    ]
    assert choose_action(TelemetrySnapshot.from_dict(data)) == MacroAction("choose_reward", {"choice_slot": 1})

    data["player"]["energy"] = 0
    data["valid_actions"] = [{"action_type": "shop_remove", "args": {"card_slot": 0}}]
    assert choose_action(TelemetrySnapshot.from_dict(data)) == MacroAction("shop_remove", {"card_slot": 0})

    data["player"]["energy"] = 1
    assert choose_action(TelemetrySnapshot.from_dict(data)) == MacroAction("shop_remove", {"card_slot": 0})

    terminal = data | {"phase": "terminal", "valid_actions": []}
    with pytest.raises(ValueError, match="no legal actions"):
        choose_action(TelemetrySnapshot.from_dict(terminal))


def test_telemetry_frame_reader_rejects_duplicate_and_out_of_order_frames() -> None:
    frame_reader = TelemetryFrameReader()
    frame = {"sequence": 1, "payload": json.loads(FIXTURE.read_text())}

    assert frame_reader.accept_json(json.dumps(frame)).sequence == 1
    with pytest.raises(ValidationError, match="duplicate"):
        frame_reader.accept_json(json.dumps(frame))
    with pytest.raises(ValidationError, match="out of order"):
        frame_reader.accept_json(json.dumps({"sequence": 0, "payload": frame["payload"]}))


def test_telemetry_frame_reader_rejects_corrupt_and_malformed_frames() -> None:
    frame_reader = TelemetryFrameReader()

    with pytest.raises(ValidationError, match="corrupt frame"):
        frame_reader.accept_json("{")
    with pytest.raises(ValidationError, match="frame must be an object"):
        frame_reader.accept_json("[]")
    with pytest.raises(ValidationError, match="sequence"):
        frame_reader.accept_json(json.dumps({"sequence": "1", "payload": {}}))


def test_telemetry_stream_client_reads_file_like_frames() -> None:
    payload = json.loads(FIXTURE.read_text())
    stream = StringIO(
        "\n".join(
            [
                "",
                json.dumps({"sequence": 1, "payload": payload}),
                json.dumps({"sequence": 2, "payload": payload}),
            ]
        )
    )
    client = TelemetryStreamClient(lambda: stream)

    assert client.next_frame().sequence == 1
    assert client.next_frame().sequence == 2
    assert client.reconnect_attempts == 0


def test_telemetry_stream_client_reconnects_after_closed_stream() -> None:
    payload = json.loads(FIXTURE.read_text())
    streams = iter(
        [
            StringIO(json.dumps({"sequence": 1, "payload": payload}) + "\n"),
            StringIO(json.dumps({"sequence": 2, "payload": payload}) + "\n"),
        ]
    )
    client = TelemetryStreamClient(lambda: next(streams))

    assert client.next_frame().sequence == 1
    assert client.next_frame().sequence == 2
    assert client.connect_attempts == 2
    assert client.reconnect_attempts == 1


def test_telemetry_stream_client_rejects_corrupt_duplicate_and_out_of_order_frames() -> None:
    payload = json.loads(FIXTURE.read_text())
    client = TelemetryStreamClient(
        lambda: StringIO(
            "\n".join(
                [
                    json.dumps({"sequence": 1, "payload": payload}),
                    "{",
                    json.dumps({"sequence": 1, "payload": payload}),
                    json.dumps({"sequence": 0, "payload": payload}),
                ]
            )
        )
    )

    assert client.next_frame().sequence == 1
    with pytest.raises(ValidationError, match="corrupt frame"):
        client.next_frame()
    with pytest.raises(ValidationError, match="duplicate"):
        client.next_frame()
    with pytest.raises(ValidationError, match="out of order"):
        client.next_frame()


def test_transition_record_is_jsonl_serializable(tmp_path: Path) -> None:
    record = TransitionRecord(
        run_id="run-1",
        state_json={"phase": "combat"},
        valid_actions_json=[{"action_type": "end_turn", "args": {}}],
        chosen_action_json={"action_type": "end_turn", "args": {}},
        reward=0.0,
        terminal=False,
        result="planned",
    )
    path = tmp_path / "records.jsonl"
    JsonlTransitionWriter(path).append(record)

    written = json.loads(path.read_text())
    assert written["run_id"] == "run-1"
    assert written["result"] == "planned"
    assert JsonlTransitionWriter(path).records()[0]["run_id"] == "run-1"
    assert JsonlTransitionWriter(tmp_path / "missing.jsonl").records() == []


def test_schema_rejects_malformed_shapes_and_arguments() -> None:
    data = json.loads(FIXTURE.read_text())
    data["player"] = []
    with pytest.raises(ValidationError, match="player must be an object"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["hand"] = {}
    with pytest.raises(ValidationError, match="hand must be a list"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["valid_actions"] = [{"action_type": "unknown", "args": {}}]
    with pytest.raises(ValidationError, match="unknown action_type"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": []}]
    with pytest.raises(ValidationError, match="args must be an object"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {}}]
    with pytest.raises(ValidationError, match="missing hand_slot"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": "0"}}]
    with pytest.raises(ValidationError, match="hand_slot must be an integer"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": -1}}]
    with pytest.raises(ValidationError, match="hand_slot must be non-negative"):
        TelemetrySnapshot.from_dict(data)


def test_schema_rejects_invalid_json_phase_empty_actions_and_player_fields() -> None:
    with pytest.raises(ValidationError, match="invalid json"):
        TelemetrySnapshot.from_json("{")
    with pytest.raises(ValidationError, match="snapshot must be an object"):
        TelemetrySnapshot.from_json("[]")

    data = json.loads(FIXTURE.read_text())
    data["phase"] = "boss"
    with pytest.raises(ValidationError, match="unknown phase"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["valid_actions"] = []
    with pytest.raises(ValidationError, match="valid_actions cannot be empty"):
        TelemetrySnapshot.from_dict(data)

    terminal = data | {"phase": "terminal"}
    assert TelemetrySnapshot.from_dict(terminal).valid_actions == []

    data = json.loads(FIXTURE.read_text())
    del data["player"]["hp"]
    with pytest.raises(ValidationError, match="player missing hp"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["player"]["hp"] = "70"
    with pytest.raises(ValidationError, match="player.hp must be an integer"):
        TelemetrySnapshot.from_dict(data)


def test_env_end_turn_block_card_and_illegal_slots() -> None:
    data = json.loads(FIXTURE.read_text())
    data["enemies"][0]["hp"] = 20
    snapshot = TelemetrySnapshot.from_dict(data)
    env = Sts2Env(snapshot)

    observation, reward, terminated, truncated, _ = env.step(1)
    assert observation["energy"] == 2
    assert reward == 0.5
    assert terminated is False
    assert truncated is False

    end_turn_state, *_ = env.step(2)
    assert end_turn_state["energy"] == 3

    with pytest.raises(ValueError, match="hand_slot"):
        env._apply_card(snapshot.to_dict(), MacroAction("play_card", {"hand_slot": 99}))
    with pytest.raises(ValueError, match="target_slot"):
        env._apply_card(snapshot.to_dict(), MacroAction("play_card", {"hand_slot": 0, "target_slot": 99}))


def test_executor_plans_all_macro_action_shapes() -> None:
    executor = MacroExecutor("Slay the Spire 2")
    actions = [
        MacroAction("choose_reward", {"choice_slot": 0}),
        MacroAction("choose_map_node", {"node_slot": 0}),
        MacroAction("choose_event_option", {"choice_slot": 0}),
        MacroAction("shop_buy", {"item_slot": 0}),
        MacroAction("shop_remove", {"card_slot": 0}),
    ]

    assert [executor.plan(action)["commands"][0]["target"] for action in actions] == [
        "reward",
        "map",
        "event_option",
        "shop",
        "shop_remove",
    ]


def test_command_and_run_record_to_dict() -> None:
    snapshot = load_snapshot()
    action = snapshot.valid_actions[0]
    command = MacroActionCommand("run-1", action, snapshot.screen_id)
    record = RunRecord("run-1", snapshot, action, reward=1.0, terminal=False, result="ok")

    assert command.to_dict()["expected_screen_id"] == "combat-1"
    assert record.to_dict()["chosen_action_json"]["action_type"] == "play_card"
