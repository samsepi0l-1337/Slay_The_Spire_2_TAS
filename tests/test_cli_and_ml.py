import json
from pathlib import Path

import torch

from sts2_tas.bc import BehavioralCloningPolicy, train_behavioral_cloning
from sts2_tas.cli import main
from sts2_tas.telemetry_schema import MacroAction


FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"
DATASET = Path(__file__).parent / "fixtures" / "ml-train-smoke.jsonl"


def test_bridge_smoke_validates_fixture(capsys) -> None:
    assert main(["bridge-smoke", "--fixture", str(FIXTURE)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["phase"] == "combat"
    assert output["valid_actions"] == 3


def test_env_step_cli_runs_one_macro_action(capsys) -> None:
    assert main(["env-step", "--snapshot", str(FIXTURE), "--action-index", "0"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["reward"] == 6.0
    assert output["terminated"] is True


def test_collect_demo_writes_heuristic_transition(tmp_path: Path) -> None:
    output = tmp_path / "demo.jsonl"

    assert main(["collect-demo", "--snapshot", str(FIXTURE), "--output", str(output)]) == 0

    line = json.loads(output.read_text())
    assert line["chosen_action_json"]["action_type"] == "play_card"


def test_train_bc_and_evaluate_policy(tmp_path: Path, capsys) -> None:
    model = tmp_path / "bc.json"

    assert main(["train-bc", "--dataset", str(DATASET), "--model", str(model)]) == 0
    assert main(["evaluate-policy", "--dataset", str(DATASET), "--model", str(model)]) == 0

    output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert output["accuracy"] == 1.0


def test_train_bc_writes_torch_model_state(tmp_path: Path) -> None:
    model = tmp_path / "bc.pt"

    train_behavioral_cloning(DATASET, model)

    artifact = torch.load(model, weights_only=False)
    assert artifact["algorithm"] == "behavioral-cloning"
    assert artifact["feature_schema"]["state_numeric_keys"] == [
        "enemy_hp_total",
        "energy",
        "floor",
        "hand_count",
        "player_hp",
    ]
    assert isinstance(artifact["model_state"]["linear.weight"], torch.Tensor)


def test_behavioral_cloning_policy_scores_unseen_state_with_torch(tmp_path: Path) -> None:
    model = tmp_path / "bc.pt"
    train_behavioral_cloning(DATASET, model)
    policy = BehavioralCloningPolicy.load(model)

    predicted = policy.predict(
        {
            "phase": "combat",
            "floor": 2,
            "player_hp": 65,
            "energy": 3,
            "enemy_hp_total": 12,
            "hand_count": 3,
        },
        [
            MacroAction("end_turn", {}),
            MacroAction("play_card", {"hand_slot": 0, "target_slot": 0}),
        ],
    )

    assert predicted == MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})


def test_behavioral_cloning_policy_falls_back_to_first_legal_action(tmp_path: Path) -> None:
    model = tmp_path / "bc.json"
    train_behavioral_cloning(DATASET, model)
    policy = BehavioralCloningPolicy.load(model)

    assert policy.predict({"phase": "unknown"}, [MacroAction("end_turn", {})]) == MacroAction("end_turn", {})


def test_legacy_behavioral_cloning_table_fallback_paths() -> None:
    play_card = {"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 0}}
    policy = BehavioralCloningPolicy(
        {json.dumps({"phase": "combat"}, sort_keys=True, separators=(",", ":")): play_card},
        {
            "state_numeric_keys": [],
            "state_categorical_values": {},
            "action_types": [],
            "action_arg_keys": [],
        },
        {},
    )

    assert policy.predict({"phase": "unknown"}, [MacroAction("end_turn", {})]) == MacroAction("end_turn", {})
    assert policy.predict(
        {"phase": "combat"},
        [MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})],
    ) == MacroAction("play_card", {"hand_slot": 0, "target_slot": 0})
    assert policy.predict({"phase": "combat"}, [MacroAction("end_turn", {})]) == MacroAction("end_turn", {})


def test_train_ppo_smoke_uses_maskable_bc_fallback(tmp_path: Path, capsys) -> None:
    model = tmp_path / "ppo.json"

    assert main(["train-ppo", "--dataset", str(DATASET), "--model", str(model), "--timesteps", "2"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["algorithm"] == "maskable-ppo-smoke"
    assert model.exists()


def test_act_cli_defaults_to_dry_run(capsys) -> None:
    action = json.dumps({"action_type": "end_turn", "args": {}})

    assert main(["act", "--action-json", action]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["execute"] is False
    assert output["commands"][0]["kind"] == "key"


def test_run_local_dry_run_loop(tmp_path: Path, capsys) -> None:
    log = tmp_path / "run.jsonl"

    assert main(["run-local", "--snapshot", str(FIXTURE), "--episodes", "1", "--output", str(log)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["episodes"] == 1
    assert output["transitions"] == 1
    assert log.exists()
