import json
from pathlib import Path

import pytest

from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot, ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def test_telemetry_snapshot_rejects_missing_required_field() -> None:
    data = json.loads(FIXTURE.read_text())
    del data["seed"]

    with pytest.raises(ValidationError, match="seed"):
        TelemetrySnapshot.from_dict(data)


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

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": True}}]
    with pytest.raises(ValidationError, match="hand_slot must be an integer"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": -1}}]
    with pytest.raises(ValidationError, match="hand_slot must be non-negative"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": 99}}]
    with pytest.raises(ValidationError, match="hand_slot out of range"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 99}}]
    with pytest.raises(ValidationError, match="target_slot out of range"):
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
    data["schema_version"] = 2
    with pytest.raises(ValidationError, match="unsupported schema_version"):
        TelemetrySnapshot.from_dict(data)

    data["schema_version"] = "1"
    with pytest.raises(ValidationError, match="schema_version must be an integer"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["valid_actions"] = []
    with pytest.raises(ValidationError, match="valid_actions cannot be empty"):
        TelemetrySnapshot.from_dict(data)

    terminal = data | {"phase": "terminal"}
    assert TelemetrySnapshot.from_dict(terminal).valid_actions == []

    terminal["valid_actions"] = [{"action_type": "end_turn", "args": {}}]
    with pytest.raises(ValidationError, match="terminal snapshots cannot expose valid_actions"):
        TelemetrySnapshot.from_dict(terminal)

    data = json.loads(FIXTURE.read_text())
    del data["player"]["hp"]
    with pytest.raises(ValidationError, match="player missing hp"):
        TelemetrySnapshot.from_dict(data)

    data = json.loads(FIXTURE.read_text())
    data["player"]["hp"] = "70"
    with pytest.raises(ValidationError, match="player.hp must be an integer"):
        TelemetrySnapshot.from_dict(data)

    data["player"]["hp"] = True
    with pytest.raises(ValidationError, match="player.hp must be an integer"):
        TelemetrySnapshot.from_dict(data)


def test_schema_validates_choice_action_slots_against_snapshot_choices() -> None:
    data = json.loads(FIXTURE.read_text())
    data["phase"] = "card_reward"
    data["reward_choices"] = [{"id": "card-a"}, {"id": "card-b"}]
    data["valid_actions"] = [{"action_type": "choose_reward", "args": {"choice_slot": 2}}]
    with pytest.raises(ValidationError, match="choice_slot out of range"):
        TelemetrySnapshot.from_dict(data)

    data["valid_actions"] = [{"action_type": "choose_reward", "args": {"choice_slot": 1}}]
    assert TelemetrySnapshot.from_dict(data).valid_actions == [MacroAction("choose_reward", {"choice_slot": 1})]
