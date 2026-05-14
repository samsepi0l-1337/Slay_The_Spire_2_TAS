import json
from pathlib import Path

from sts2_tas import cli
from sts2_tas.metrics import model_evaluation_metrics, play_evaluation_metrics
from sts2_tas.model import CandidateRecommendation, Recommendation
from sts2_tas.schema import ActionCandidate, GameStep, ObservationQuality, PlayerState, StepOutcome, StructuredGameState
from sts2_tas.torch_dataset import write_game_steps


def _step(chosen: str = "anger") -> GameStep:
    actions = [
        ActionCandidate(action_type="pick_card", option_id="anger", legal=True),
        ActionCandidate(action_type="skip_reward", option_id="skip", legal=True),
        ActionCandidate(action_type="play_card", source_card_id="strike", legal=False),
    ]
    aliases = {"anger": actions[0].identity, "skip": actions[1].identity}
    return GameStep(
        state=StructuredGameState(
            game_version="0.105.1",
            branch="beta",
            catalog_version="test-catalog",
            character="ironclad",
            ascension=0,
            floor=1,
            decision_context="card_reward",
            player=PlayerState(hp=70, max_hp=80, block=0, energy=3, turn=1),
        ),
        actions=actions,
        chosen_action_id=aliases[chosen],
        outcome=None,
        observation=ObservationQuality("screen", 1.0, "0.105.1", "beta", "test-catalog"),
        screenshot_path=Path("fixture.png"),
    )


def test_evaluate_model_cli_writes_policy_and_value_metrics(tmp_path: Path, monkeypatch) -> None:
    dataset = tmp_path / "steps.jsonl"
    out = tmp_path / "model-eval.json"
    self_labeled = GameStep(
        state=_step("anger").state,
        actions=_step("anger").actions,
        chosen_action_id=_step("anger").chosen_action_id,
        outcome=None,
        observation=_step("anger").observation,
        screenshot_path=Path("fixture.png"),
        label_source="model_self",
    )
    write_game_steps(dataset, [_step("anger"), _step("skip"), self_labeled])

    def fake_recommend(_model, step: GameStep) -> Recommendation:
        anger, skip = step.actions[:2]
        scores = [0.9, 0.1] if step.chosen_action_id == anger.identity else [0.7, 0.3]
        return Recommendation(
            best=CandidateRecommendation(anger.identity, anger.action_type, anger.option_id, scores[0]),
            candidates=[
                CandidateRecommendation(anger.identity, anger.action_type, anger.option_id, scores[0]),
                CandidateRecommendation(skip.identity, skip.action_type, skip.option_id, scores[1]),
            ],
        )

    monkeypatch.setattr("sts2_tas.evaluation_cli.load_model", lambda path: object())
    monkeypatch.setattr("sts2_tas.evaluation_cli.recommend", fake_recommend)

    exit_code = cli.main(["evaluate-model", "--dataset", str(dataset), "--model", str(tmp_path / "m.pt"), "--character", "ironclad", "--out", str(out)])

    metrics = json.loads(out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert metrics == {
        "brier_score": 0.25,
        "evaluated_steps": 2,
        "legal_action_mask_accuracy": 1.0,
        "score_margin_correct": 0.8,
        "score_margin_incorrect": 0.39999999999999997,
        "top_1_accuracy": 0.5,
        "top_3_accuracy": 1.0,
        "value_correlation": 0.0,
    }


def test_evaluate_play_cli_writes_episode_quality_metrics(tmp_path: Path) -> None:
    episodes = tmp_path / "episodes.jsonl"
    out = tmp_path / "play-eval.json"
    episodes.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed": 7,
                        "victory": True,
                        "floor": 20,
                        "hp_remaining": 44,
                        "steps": 12,
                        "decision_latency_ms": 30,
                        "transition_timeout": False,
                        "misclicks": 0,
                        "illegal_actions": 0,
                        "candidate_recall": 1.0,
                    }
                ),
                json.dumps(
                    {
                        "seed": 8,
                        "victory": False,
                        "floor": 10,
                        "hp_remaining": 0,
                        "steps": 8,
                        "decision_latency_ms": 50,
                        "transition_timeout": True,
                        "misclicks": 1,
                        "illegal_actions": 2,
                        "candidate_recall": 0.5,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = cli.main(["evaluate-play", "--episodes", str(episodes), "--out", str(out)])

    assert exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "average_floor": 15.0,
        "average_hp_remaining": 22.0,
        "average_steps": 10.0,
        "candidate_recall": 0.75,
        "decision_latency_ms": 40.0,
        "episodes": 2,
        "illegal_action_rate": 1.0,
        "misclick_rate": 0.5,
        "transition_timeout_rate": 0.5,
        "win_rate": 0.5,
    }


def test_model_metrics_cover_empty_missing_scores_and_value_correlation() -> None:
    anger = _step("anger")
    skip = GameStep(
        state=_step("skip").state,
        actions=_step("skip").actions,
        chosen_action_id=_step("skip").chosen_action_id,
        outcome=StepOutcome(False, 0, 0, value_target=0.0),
        observation=_step("skip").observation,
        screenshot_path=Path("fixture.png"),
    )
    anger = GameStep(
        state=anger.state,
        actions=anger.actions,
        chosen_action_id=anger.chosen_action_id,
        outcome=StepOutcome(True, 0, 0, value_target=1.0),
        observation=anger.observation,
        screenshot_path=Path("fixture.png"),
    )
    empty = Recommendation(best=CandidateRecommendation("missing", "missing", None, 0.0), candidates=[])
    correct = Recommendation(
        best=CandidateRecommendation(anger.chosen_action_id, "pick_card", "anger", 0.8),
        candidates=[CandidateRecommendation(anger.chosen_action_id, "pick_card", "anger", 0.8)],
    )

    assert model_evaluation_metrics([])["evaluated_steps"] == 0
    metrics = model_evaluation_metrics([(anger, correct), (skip, empty)])
    assert metrics["value_correlation"] > 0.0
    assert metrics["legal_action_mask_accuracy"] == 0.5
    assert metrics["score_margin_incorrect"] == 0.0
    assert play_evaluation_metrics([])["episodes"] == 0


def test_model_metrics_skip_unlabeled_rows_and_zero_variance_value_correlation() -> None:
    labeled = GameStep(
        state=_step("anger").state,
        actions=_step("anger").actions,
        chosen_action_id=_step("anger").chosen_action_id,
        outcome=StepOutcome(True, 0, 0, value_target=1.0),
        observation=_step("anger").observation,
        screenshot_path=Path("fixture.png"),
    )
    unlabeled = GameStep(labeled.state, labeled.actions, None, labeled.outcome, labeled.observation, labeled.screenshot_path)
    recommendation = Recommendation(
        best=CandidateRecommendation(labeled.chosen_action_id, "pick_card", "anger", 0.8),
        candidates=[CandidateRecommendation(labeled.chosen_action_id, "pick_card", "anger", 0.8)],
    )

    metrics = model_evaluation_metrics([(unlabeled, recommendation), (labeled, recommendation), (labeled, recommendation)])

    assert metrics["evaluated_steps"] == 2
    assert metrics["value_correlation"] == 0.0
