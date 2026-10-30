import json
from pathlib import Path

import torch

from sts2_tas.bc import BehavioralCloningPolicy, evaluate_behavioral_cloning, train_behavioral_cloning
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
    assert line["chosen_action"]["action_type"] == "play_card"
    assert line["state"] == line["state_json"]
    assert line["valid_actions"] == line["valid_actions_json"]


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


def test_behavioral_cloning_policy_rejects_empty_legal_actions(tmp_path: Path) -> None:
    model = tmp_path / "bc.json"
    train_behavioral_cloning(DATASET, model)
    policy = BehavioralCloningPolicy.load(model)

    try:
        policy.predict({"phase": "terminal"}, [])
    except ValueError as exc:
        assert "no legal actions" in str(exc)
    else:
        raise AssertionError("empty legal actions must fail closed")


def test_evaluate_behavioral_cloning_skips_empty_terminal_samples(tmp_path: Path) -> None:
    model = tmp_path / "bc.json"
    dataset = tmp_path / "with-terminal.jsonl"
    train_behavioral_cloning(DATASET, model)
    lines = DATASET.read_text().splitlines()
    terminal = {
        "state": {"phase": "terminal"},
        "valid_actions": [],
        "chosen_action": {"action_type": "end_turn", "args": {}},
    }
    dataset.write_text("\n".join([json.dumps(terminal), *lines]))

    result = evaluate_behavioral_cloning(dataset, model)

    assert result["samples"] == 2
    assert result["accuracy"] == 1.0


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


def test_train_ppo_smoke_preserves_torch_artifact(tmp_path: Path) -> None:
    model = tmp_path / "ppo.pt"

    assert main(["train-ppo", "--dataset", str(DATASET), "--model", str(model), "--timesteps", "2"]) == 0

    artifact = torch.load(model, weights_only=False)
    assert artifact["algorithm"] == "maskable-ppo-smoke"
    assert artifact["timesteps"] == 2
    assert isinstance(artifact["model_state"]["linear.weight"], torch.Tensor)


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


def test_cli_reports_input_failure_without_success_json(tmp_path, capsys) -> None:
    assert main(["bridge-smoke", "--fixture", str(tmp_path / "missing.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "sts2-tas:" in captured.err
    assert "missing.json" in captured.err


def test_cli_reports_unsupported_native_execution(monkeypatch, capsys) -> None:
    def fail(_self, _action):
        raise NotImplementedError("native input backend is not implemented")

    monkeypatch.setattr("sts2_tas.cli.MacroExecutor.execute", fail)
    assert main(["act", "--action-json", '{"action_type":"end_turn","args":{}}', "--execute"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "sts2-tas: native input backend is not implemented\n"


def test_cli_interrupt_returns_conventional_exit(monkeypatch, capsys) -> None:
    def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr("sts2_tas.cli._bridge_smoke", interrupt)
    assert main(["bridge-smoke", "--fixture", str(FIXTURE)]) == 130
    assert capsys.readouterr().out == ""


def test_cli_command_without_result_does_not_print(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sts2_tas.cli._bridge_smoke", lambda _args: None)
    assert main(["bridge-smoke", "--fixture", str(FIXTURE)]) == 0
    assert capsys.readouterr().out == ""


def test_live_cli_closes_writer_even_when_reader_close_fails(monkeypatch, tmp_path) -> None:
    import io

    class BrokenReader(io.StringIO):
        def close(self):
            super().close()
            raise OSError("reader close failed")

    reader, writer = BrokenReader(), io.StringIO()
    monkeypatch.setattr("sts2_tas.cli.connect_transport", lambda _spec: (reader, writer))
    monkeypatch.setattr("sts2_tas.cli.run_live", lambda *_args, **_kwargs: {})
    assert main(["run-live", "--model", str(tmp_path / "model.json"), "--output", str(tmp_path / "log.jsonl")]) == 1
    assert reader.closed
    assert writer.closed


def test_live_cli_closes_shared_pipe_once_on_failure(monkeypatch, tmp_path) -> None:
    import io

    class CountingPipe(io.StringIO):
        closes = 0

        def close(self):
            self.closes += 1
            super().close()

    pipe = CountingPipe()
    monkeypatch.setattr("sts2_tas.cli.connect_transport", lambda _spec: (pipe, pipe))

    def fail(*_args, **_kwargs):
        raise ValueError("bad frame")

    monkeypatch.setattr("sts2_tas.cli.run_live", fail)
    assert main(["run-live", "--model", str(tmp_path / "model.json"), "--output", str(tmp_path / "log.jsonl")]) == 1
    assert pipe.closed
    assert pipe.closes == 1
