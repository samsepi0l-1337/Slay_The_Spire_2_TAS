import json
from pathlib import Path

from sts2_tas.cli import main
from sts2_tas.env import Sts2Env
from sts2_tas.executor import MacroExecutor
from sts2_tas.qstar import FEATURE_DIM, QStarPolicy, feature_vector, run_qstar, simulate
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def load_snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot.from_json(FIXTURE.read_text())


def combat_data(**overrides: object) -> dict:
    data = json.loads(FIXTURE.read_text())
    data.update(overrides)
    return data


def test_env_rebuilds_actions_after_nonlethal_card_and_skips_unaffordable() -> None:
    data = combat_data()
    data["enemies"][0]["hp"] = 20
    data["player"]["energy"] = 1
    env = Sts2Env(TelemetrySnapshot.from_dict(data))

    observation, reward, terminated, _, _ = env.step(0)

    assert terminated is False
    assert reward == 6.0
    assert observation["energy"] == 0
    assert [card["id"] for card in env.snapshot.hand] == ["defend"]
    assert env.snapshot.valid_actions == [MacroAction("end_turn", {})]


def test_env_end_turn_redraws_from_draw_then_discard() -> None:
    data = combat_data()
    data["enemies"][0]["hp"] = 20
    data["draw_pile"] = [{"id": "bash", "name": "Bash", "cost": 2, "type": "attack", "damage": 8}]
    env = Sts2Env(TelemetrySnapshot.from_dict(data))
    env.step(1)

    observation, reward, terminated, _, _ = env.step(env.action_space.index_of(MacroAction("end_turn", {})))

    assert terminated is False
    assert reward == 0.0
    assert observation["energy"] == 3
    assert [card["id"] for card in env.snapshot.hand] == ["bash", "defend", "strike"]


def test_env_end_turn_with_empty_piles_keeps_only_end_turn() -> None:
    data = combat_data()
    data["hand"] = []
    data["draw_pile"] = []
    data["discard_pile"] = []
    data["valid_actions"] = [{"action_type": "end_turn", "args": {}}]
    env = Sts2Env(TelemetrySnapshot.from_dict(data))

    observation, _, terminated, _, _ = env.step(0)

    assert terminated is False
    assert observation["hand_count"] == 0
    assert env.snapshot.valid_actions == [MacroAction("end_turn", {})]


def test_env_rebuilds_targets_only_for_living_enemies() -> None:
    data = combat_data()
    data["enemies"] = [
        {"id": "a", "slot": 0, "hp": 6, "block": 0, "intent": "attack", "powers": []},
        {"id": "b", "slot": 1, "hp": 20, "block": 0, "intent": "attack", "powers": []},
    ]
    data["valid_actions"] = [
        {"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 0}},
        {"action_type": "play_card", "args": {"hand_slot": 0, "target_slot": 1}},
        {"action_type": "play_card", "args": {"hand_slot": 1}},
        {"action_type": "end_turn", "args": {}},
    ]
    env = Sts2Env(TelemetrySnapshot.from_dict(data))
    env.step(0)

    assert env.snapshot.enemies[0]["hp"] == 0
    assert env.snapshot.valid_actions == [
        MacroAction("play_card", {"hand_slot": 0}),
        MacroAction("end_turn", {}),
    ]


def test_feature_vector_encodes_lethal_choice_slots_and_missing_cards() -> None:
    snapshot = load_snapshot()
    strike = snapshot.valid_actions[0]
    features = feature_vector(snapshot, strike)

    assert len(features) == FEATURE_DIM
    assert features[-1] == 1.0
    assert feature_vector(snapshot, snapshot.valid_actions[1])[-1] == 0.0
    assert feature_vector(snapshot, MacroAction("end_turn", {}))[19] == 0.0
    assert feature_vector(snapshot, MacroAction("choose_reward", {"choice_slot": 2}))[19] == 0.2
    assert feature_vector(snapshot, MacroAction("choose_map_node", {"node_slot": 3}))[19] == 0.3
    assert feature_vector(snapshot, MacroAction("shop_buy", {"item_slot": 4}))[19] == 0.4
    assert feature_vector(snapshot, MacroAction("shop_remove", {"card_slot": 5}))[19] == 0.5
    assert feature_vector(snapshot, MacroAction("play_card", {"hand_slot": 99}))[20] == 0.0
    assert feature_vector(snapshot, MacroAction("play_card", {"hand_slot": -1}))[20] == 0.0
    assert feature_vector(snapshot, MacroAction("play_card", {"hand_slot": 0, "target_slot": 99}))[-1] == 0.0

    dead = combat_data()
    dead["enemies"][0]["hp"] = 0
    assert feature_vector(TelemetrySnapshot.from_dict(dead), strike)[-1] == 0.0


def test_qstar_update_increases_value_of_played_action() -> None:
    snapshot = load_snapshot()
    action = snapshot.valid_actions[0]
    policy = QStarPolicy()
    before = policy.q_value(snapshot, action)
    nxt, reward, terminated = simulate(snapshot, action)
    policy.update(snapshot, action, reward, nxt, terminated)

    assert terminated is True
    assert policy.q_value(snapshot, action) > before
    assert policy.updates == 1


def test_qstar_search_uses_env_reward_over_myopic_weights() -> None:
    snapshot = load_snapshot()
    defend = MacroAction("play_card", {"hand_slot": 1})
    policy = QStarPolicy()
    nxt, reward, terminated = simulate(snapshot, defend)
    policy.update(snapshot, defend, reward, nxt, terminated)

    assert policy.select(snapshot, search_depth=0) == defend
    assert policy.select(snapshot, search_depth=1) == snapshot.valid_actions[0]


def test_qstar_select_rejects_empty_legal_actions() -> None:
    policy = QStarPolicy()
    data = combat_data(phase="terminal", valid_actions=[])

    try:
        policy.select(TelemetrySnapshot.from_dict(data))
    except ValueError as exc:
        assert "no legal actions" in str(exc)
    else:
        raise AssertionError("empty legal actions must fail closed")


def test_qstar_save_load_json_pt_and_rejects_other_algorithms(tmp_path: Path) -> None:
    snapshot = load_snapshot()
    policy = QStarPolicy(gamma=0.5, alpha=0.1)
    nxt, reward, terminated = simulate(snapshot, snapshot.valid_actions[0])
    policy.update(snapshot, snapshot.valid_actions[0], reward, nxt, terminated)
    json_path = tmp_path / "qstar.json"
    pt_path = tmp_path / "qstar.pt"
    policy.save(json_path)
    policy.save(pt_path)

    loaded_json = QStarPolicy.load(json_path)
    loaded_pt = QStarPolicy.load(pt_path)
    assert loaded_json.gamma == 0.5
    assert loaded_pt.alpha == 0.1
    assert loaded_json.updates == 1
    assert loaded_pt.q_value(snapshot, snapshot.valid_actions[0]) == policy.q_value(snapshot, snapshot.valid_actions[0])
    assert QStarPolicy.load_or_create(json_path).updates == 1
    assert QStarPolicy.load_or_create(tmp_path / "missing.json").updates == 0

    other = tmp_path / "bc.json"
    other.write_text(json.dumps({"algorithm": "behavioral-cloning"}))
    try:
        QStarPolicy.load(other)
    except ValueError as exc:
        assert "unsupported algorithm" in str(exc)
    else:
        raise AssertionError("non-qstar artifacts must fail closed")

    sparse = tmp_path / "sparse.json"
    sparse.write_text(
        json.dumps(
            {
                "algorithm": "qstar",
                "model_state": {"linear.weight": [[0.0] * FEATURE_DIM], "linear.bias": [0.0]},
            }
        )
    )
    restored = QStarPolicy.load(sparse)
    assert restored.gamma == 0.95
    assert restored.alpha == 0.05
    assert restored.updates == 0


def test_run_qstar_plays_until_terminal_and_writes_weights(tmp_path: Path) -> None:
    model = tmp_path / "qstar.json"
    output = tmp_path / "run.jsonl"
    snapshot = load_snapshot()
    executor = MacroExecutor("Slay the Spire 2")

    first = run_qstar(snapshot, model, output, episodes=2, search_depth=1, executor=executor)
    second = run_qstar(snapshot, model, output, episodes=1, search_depth=1)

    assert first["algorithm"] == "qstar"
    assert first["transitions"] >= 2
    assert first["updates"] == first["transitions"]
    assert first["plans"] == first["transitions"]
    assert second["updates"] == first["updates"] + second["transitions"]
    assert second["plans"] == 0
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == first["transitions"] + second["transitions"]
    assert records[0]["policy_id"] == "qstar"
    assert any(record["terminal"] for record in records)
    artifact = json.loads(model.read_text())
    assert artifact["algorithm"] == "qstar"
    assert artifact["updates"] == second["updates"]


def test_run_qstar_stops_at_max_steps_and_skips_terminal_snapshots(tmp_path: Path) -> None:
    data = combat_data()
    data["enemies"][0]["hp"] = 40
    model = tmp_path / "qstar.pt"
    output = tmp_path / "run.jsonl"

    truncated = run_qstar(TelemetrySnapshot.from_dict(data), model, output, search_depth=1, max_steps=2)
    empty = run_qstar(
        TelemetrySnapshot.from_dict(combat_data(phase="terminal", valid_actions=[])),
        tmp_path / "empty.json",
        tmp_path / "empty.jsonl",
    )

    assert truncated["transitions"] == 2
    assert model.exists()
    assert empty["transitions"] == 0
    assert empty["updates"] == 0


def test_run_qstar_cli_updates_weights_and_honors_execute(tmp_path: Path, capsys) -> None:
    model = tmp_path / "qstar.json"
    output = tmp_path / "run.jsonl"

    assert (
        main(
            [
                "run-qstar",
                "--snapshot",
                str(FIXTURE),
                "--model",
                str(model),
                "--output",
                str(output),
                "--episodes",
                "2",
                "--search-depth",
                "1",
                "--max-steps",
                "8",
                "--execute",
            ]
        )
        == 0
    )

    result = json.loads(capsys.readouterr().out)
    assert result["algorithm"] == "qstar"
    assert result["episodes"] == 2
    assert result["transitions"] >= 2
    assert result["updates"] == result["transitions"]
    assert result["plans"] == result["transitions"]
    assert json.loads(model.read_text())["updates"] == result["updates"]
