import json
import pickle
from pathlib import Path

import pytest
import torch

from sts2_tas.bc import BehavioralCloningPolicy, train_behavioral_cloning
from sts2_tas.qstar import QStarPolicy
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


DATASET = Path(__file__).parent / "fixtures" / "ml-train-smoke.jsonl"
SNAPSHOT = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def _write_marker(path: str) -> dict:
    Path(path).touch()
    return {"algorithm": "qstar", "table": {}, "model_state": {}}


class _PickleCallback:
    def __init__(self, marker: Path) -> None:
        self.marker = marker

    def __reduce__(self):
        return _write_marker, (str(self.marker),)


@pytest.mark.parametrize("loader", [BehavioralCloningPolicy.load, QStarPolicy.load])
def test_model_load_rejects_pickle_callbacks_without_executing_them(tmp_path, loader):
    marker = tmp_path / "callback-ran"
    artifact = tmp_path / "unsafe.pt"
    torch.save(_PickleCallback(marker), artifact)

    with pytest.raises(pickle.UnpicklingError):
        loader(artifact)

    assert not marker.exists()


def test_bc_training_and_prediction_preserve_torch_rng(tmp_path):
    torch.manual_seed(123)
    before = torch.get_rng_state().clone()
    policy = train_behavioral_cloning(DATASET, tmp_path / "bc.pt")
    assert torch.equal(torch.get_rng_state(), before)

    sample = json.loads(DATASET.read_text().splitlines()[0])
    actions = [MacroAction.from_dict(action) for action in sample["valid_actions"]]
    assert policy.predict(sample["state"], actions) == MacroAction.from_dict(sample["chosen_action"])
    assert torch.equal(torch.get_rng_state(), before)


def test_qstar_creation_is_reproducible_without_changing_torch_rng():
    before = torch.get_rng_state().clone()
    first = QStarPolicy()
    assert torch.equal(torch.get_rng_state(), before)
    second = QStarPolicy()
    assert all(torch.equal(value, second.model.state_dict()[key]) for key, value in first.model.state_dict().items())


@pytest.mark.parametrize("content", ["", "\n", json.dumps({"state": {"phase": "terminal"}, "valid_actions": []})])
def test_bc_training_rejects_dataset_without_demonstrations(tmp_path, content):
    dataset = tmp_path / "empty.jsonl"
    dataset.write_text(content)
    model = tmp_path / "bc.pt"

    with pytest.raises(ValueError, match="no actionable demonstrations"):
        train_behavioral_cloning(dataset, model)

    assert not model.exists()


@pytest.mark.parametrize("change, message", [
    ({"state": []}, "state must be an object"),
    ({"valid_actions": {}}, "valid_actions must be a list"),
    ({"valid_actions": []}, "empty legal actions"),
    ({"chosen_action": {"action_type": "choose_reward", "args": {"choice_slot": 0}}}, "chosen action is not legal"),
])
def test_bc_training_validates_samples_before_writing(tmp_path, change, message):
    sample = json.loads(DATASET.read_text().splitlines()[0])
    sample.update(change)
    dataset = tmp_path / "invalid.jsonl"
    dataset.write_text(json.dumps(sample))
    model = tmp_path / "existing.pt"
    model.write_bytes(b"preserve existing model")

    with pytest.raises(ValueError, match=message):
        train_behavioral_cloning(dataset, model)

    assert model.read_bytes() == b"preserve existing model"


def test_bc_training_skips_terminal_rows(tmp_path):
    dataset = tmp_path / "terminal.jsonl"
    dataset.write_text(json.dumps({"state": {"phase": "terminal"}, "valid_actions": []}) + "\n" + DATASET.read_text())
    policy = train_behavioral_cloning(dataset, tmp_path / "bc.json")
    assert len(policy.table) == 2


@pytest.mark.parametrize("corruption", ["feature_version", "missing_layer"])
def test_qstar_incompatible_checkpoint_resets_all_weights(tmp_path, corruption):
    source = QStarPolicy(updates=9)
    with torch.no_grad():
        for parameter in source.model.parameters():
            parameter.fill_(7.0)
    model = tmp_path / "incompatible.json"
    source.save(model)
    artifact = json.loads(model.read_text())
    if corruption == "feature_version":
        artifact["feature_version"] += 1
    else:
        del artifact["model_state"]["net.2.bias"]
    model.write_text(json.dumps(artifact))

    restored = QStarPolicy.load(model)
    snapshot = TelemetrySnapshot.from_json(SNAPSHOT.read_text())
    fresh = QStarPolicy()
    assert restored.updates == 0
    assert restored.q_value(snapshot, snapshot.valid_actions[0]) == 0.0
    assert all(torch.equal(value, fresh.model.state_dict()[key]) for key, value in restored.model.state_dict().items())
