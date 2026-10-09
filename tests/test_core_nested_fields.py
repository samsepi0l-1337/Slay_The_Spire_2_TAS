import json
from pathlib import Path

import pytest

from sts2_tas.telemetry_client import TelemetryFrameReader
from sts2_tas.telemetry_schema import TelemetrySnapshot, ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


@pytest.mark.parametrize(
    "field,key,value",
    [
        ("hand", "damage", "bad"),
        ("hand", "cost", None),
        ("hand", "block", True),
        ("draw_pile", "damage", "bad"),
        ("discard_pile", "cost", []),
        ("exhaust_pile", "block", 1.5),
        ("enemies", "hp", "bad"),
        ("enemies", "block", {}),
    ],
)
def test_frame_reader_rejects_consumed_entity_numbers(field, key, value):
    data = json.loads(FIXTURE.read_text())
    if not data[field]:
        data[field] = [{"id": "card"}]
    data[field][0][key] = value
    reader = TelemetryFrameReader()
    with pytest.raises(ValidationError, match=rf"{field}\[0\].{key} must be an integer"):
        reader.accept_json(json.dumps({"sequence": 1, "payload": data}))
    valid = json.loads(FIXTURE.read_text())
    assert reader.accept_json(json.dumps({"sequence": 1, "payload": valid})).sequence == 1


@pytest.mark.parametrize("resources", [[1], None, "bad"])
def test_snapshot_rejects_non_object_player_resources(resources):
    data = json.loads(FIXTURE.read_text())
    data["player"]["resources"] = resources
    with pytest.raises(ValidationError, match="player.resources must be an object"):
        TelemetrySnapshot.from_dict(data)


@pytest.mark.parametrize("value", ["bad", True, 1.5])
def test_snapshot_rejects_non_integer_stars_and_ascension(value):
    data = json.loads(FIXTURE.read_text())
    data["player"]["resources"]["stars"] = value
    with pytest.raises(ValidationError, match="player.resources.stars must be an integer"):
        TelemetrySnapshot.from_dict(data)
    data["player"]["resources"] = {}
    data.setdefault("extras", {})["ascension"] = value
    with pytest.raises(ValidationError, match="extras.ascension must be an integer"):
        TelemetrySnapshot.from_dict(data)


def test_snapshot_keeps_optional_defaults_and_integer_card_cost_sentinels():
    data = json.loads(FIXTURE.read_text())
    data["hand"][0]["cost"] = -1
    del data["hand"][0]["damage"]
    del data["enemies"][0]["block"]
    del data["player"]["resources"]
    snapshot = TelemetrySnapshot.from_dict(data)
    assert snapshot.hand[0]["cost"] == -1
    assert "damage" not in snapshot.hand[0]
    assert "resources" not in snapshot.player


@pytest.mark.parametrize(
    "key,value,expected_type",
    [
        ("id", {}, "a string"),
        ("id", None, "a string"),
        ("slot", [], "an integer"),
        ("slot", True, "an integer"),
    ],
)
def test_frame_reader_rejects_unhashable_or_invalid_enemy_identity(key, value, expected_type):
    data = json.loads(FIXTURE.read_text())
    data["enemies"][0][key] = value
    reader = TelemetryFrameReader()
    with pytest.raises(ValidationError, match=rf"enemies\[0\].{key} must be {expected_type}"):
        reader.accept_json(json.dumps({"sequence": 1, "payload": data}))
    valid = json.loads(FIXTURE.read_text())
    assert reader.accept_json(json.dumps({"sequence": 1, "payload": valid})).sequence == 1


def test_snapshot_preserves_missing_enemy_identity_defaults():
    data = json.loads(FIXTURE.read_text())
    del data["enemies"][0]["id"]
    del data["enemies"][0]["slot"]
    snapshot = TelemetrySnapshot.from_dict(data)
    assert snapshot.enemies[0].get("id") is None
    assert snapshot.enemies[0].get("slot") is None
