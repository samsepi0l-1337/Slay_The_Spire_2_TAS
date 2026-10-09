import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from sts2_tas.action_space import ActionSpace
from sts2_tas.env import Sts2Env
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot, ValidationError


FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def snapshot_data():
    return json.loads(FIXTURE.read_text())


def test_snapshot_capture_and_serialization_isolate_nested_state():
    data = snapshot_data()
    snapshot = TelemetrySnapshot.from_dict(data)
    data["hand"][0]["damage"] = 99
    assert snapshot.hand[0]["damage"] == 6
    exported = snapshot.to_dict()
    exported["player"]["powers"].append({"id": "external"})
    exported["enemies"][0]["hp"] = 0
    assert snapshot.player["powers"] == []
    assert snapshot.enemies[0]["hp"] == 6


def test_env_step_preserves_input_snapshot_and_reset_restores_episode():
    snapshot = TelemetrySnapshot.from_dict(snapshot_data())
    original = deepcopy(snapshot.to_dict())
    env = Sts2Env(snapshot)
    env.step(0)
    assert snapshot.to_dict() == original
    observation, info = env.reset(seed=42)
    assert observation["phase"] == "combat"
    assert observation["energy"] == 3
    assert info == {"seed": 42, "valid_action_mask": [True, True, True]}
    assert env.snapshot.to_dict() == original
    assert env.step(0)[2] is True


@pytest.mark.parametrize("index", [True, False, 0.0, "0", None])
def test_action_space_rejects_non_integer_indices(index):
    env = Sts2Env(TelemetrySnapshot.from_dict(snapshot_data()))
    before = env.snapshot.to_dict()
    with pytest.raises(ValueError, match="illegal action"):
        env.step(index)
    assert env.snapshot.to_dict() == before


def test_action_space_accepts_numpy_integer_policy_output():
    space = ActionSpace.from_snapshot(TelemetrySnapshot.from_dict(snapshot_data()))
    assert space.action_at(np.int64(0)) == space.actions[0]


@pytest.mark.parametrize("field,value", [("phase", []), ("extras", []), ("extras", None)])
def test_snapshot_rejects_invalid_object_fields(field, value):
    data = snapshot_data()
    data[field] = value
    with pytest.raises(ValidationError):
        TelemetrySnapshot.from_dict(data)


@pytest.mark.parametrize("action", [None, [], {"action_type": [], "args": {}}])
def test_snapshot_rejects_invalid_action_objects(action):
    data = snapshot_data()
    data["valid_actions"] = [action]
    with pytest.raises(ValidationError):
        TelemetrySnapshot.from_dict(data)


@pytest.mark.parametrize("timestamp", [True, "bad", float("nan"), float("inf"), None])
def test_snapshot_rejects_non_finite_or_non_numeric_timestamps(timestamp):
    data = snapshot_data()
    data["timestamp"] = timestamp
    with pytest.raises(ValidationError, match="timestamp"):
        TelemetrySnapshot.from_dict(data)


def test_macro_rejects_unknown_argument_instead_of_ignoring_it():
    with pytest.raises(ValidationError, match="unexpected argument"):
        MacroAction.from_dict({"action_type": "end_turn", "args": {"hand_slot": 0}})


def test_executor_enabled_fails_without_native_backend():
    from sts2_tas.executor import MacroExecutor

    with pytest.raises(NotImplementedError, match="native input backend"):
        MacroExecutor("Slay the Spire 2", execute_enabled=True).execute(MacroAction("end_turn", {}))


@pytest.mark.parametrize("field", ["hand", "enemies", "draw_pile", "reward_choices", "relics"])
def test_snapshot_rejects_non_object_entity_entries(field):
    data = snapshot_data()
    data[field] = ["not-an-object"]
    with pytest.raises(ValidationError, match=f"{field} entries must be objects"):
        TelemetrySnapshot.from_dict(data)


@pytest.mark.parametrize("parser", [MacroAction.from_dict, TelemetrySnapshot.from_dict])
def test_dict_parsers_reject_non_object_root(parser):
    with pytest.raises(ValidationError, match="expected an object"):
        parser(None)


def test_env_captures_actions_independently_from_input_snapshot():
    snapshot = TelemetrySnapshot.from_dict(snapshot_data())
    env = Sts2Env(snapshot)
    snapshot.valid_actions[0].args["hand_slot"] = 99
    assert env.action_space.actions[0].args["hand_slot"] == 0
    assert env.step(0)[2] is True
