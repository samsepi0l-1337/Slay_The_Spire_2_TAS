from __future__ import annotations

import math
from typing import Any, Iterable

from .ml_schema import GameStep
from .model import Recommendation
from .trajectory import value_target_for_step


def model_evaluation_metrics(rows: Iterable[tuple[GameStep, Recommendation]]) -> dict[str, float | int]:
    total = 0
    top_1 = 0
    top_3 = 0
    legal_mask = 0
    brier_sum = 0.0
    correct_margins: list[float] = []
    incorrect_margins: list[float] = []
    predicted_values: list[float] = []
    target_values: list[float] = []
    for step, recommendation in rows:
        if step.chosen_action_id is None:
            continue
        total += 1
        ranked = recommendation.candidates
        legal_ids = {action.identity for action in step.actions if action.legal}
        candidate_ids = [candidate.action_id for candidate in ranked]
        legal_mask += int(bool(candidate_ids) and all(action_id in legal_ids for action_id in candidate_ids))
        selected_score = _score_for(ranked, step.chosen_action_id)
        brier_sum += (1.0 - selected_score) ** 2
        top_1 += int(bool(ranked) and ranked[0].action_id == step.chosen_action_id)
        top_3 += int(step.chosen_action_id in candidate_ids[:3])
        margin = _top_margin(ranked, step.chosen_action_id, selected_score)
        if bool(ranked) and ranked[0].action_id == step.chosen_action_id:
            correct_margins.append(margin)
        else:
            incorrect_margins.append(margin)
        if step.outcome is not None:
            predicted_values.append(selected_score)
            target_values.append(value_target_for_step(step))
    return {
        "top_1_accuracy": top_1 / total if total else 0.0,
        "top_3_accuracy": top_3 / total if total else 0.0,
        "legal_action_mask_accuracy": legal_mask / total if total else 0.0,
        "value_correlation": _correlation(predicted_values, target_values),
        "brier_score": round(brier_sum / total, 12) if total else 0.0,
        "score_margin_correct": _mean(correct_margins),
        "score_margin_incorrect": _mean(incorrect_margins),
        "evaluated_steps": total,
    }


def play_evaluation_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    episodes = len(rows)
    return {
        "episodes": episodes,
        "win_rate": _mean([1.0 if row.get("victory") is True else 0.0 for row in rows]),
        "average_floor": _mean([float(row.get("floor", row.get("floor_reached", 0))) for row in rows]),
        "average_hp_remaining": _mean([float(row.get("hp_remaining", 0)) for row in rows]),
        "average_steps": _mean([float(row.get("steps", 0)) for row in rows]),
        "decision_latency_ms": _mean([float(row.get("decision_latency_ms", 0.0)) for row in rows]),
        "transition_timeout_rate": _mean([1.0 if row.get("transition_timeout") else 0.0 for row in rows]),
        "misclick_rate": sum(float(row.get("misclicks", 0)) for row in rows) / episodes if episodes else 0.0,
        "illegal_action_rate": sum(float(row.get("illegal_actions", 0)) for row in rows) / episodes if episodes else 0.0,
        "candidate_recall": _mean([float(row.get("candidate_recall", 0.0)) for row in rows]),
    }


def _score_for(candidates, action_id: str) -> float:
    for candidate in candidates:
        if candidate.action_id == action_id:
            return float(candidate.score)
    return 0.0


def _top_margin(candidates, action_id: str, selected_score: float) -> float:
    if not candidates:
        return 0.0
    if candidates[0].action_id == action_id:
        runner_up = float(candidates[1].score) if len(candidates) > 1 else 0.0
        return selected_score - runner_up
    return float(candidates[0].score) - selected_score


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(ys) < 2:
        return 0.0
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denominator_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denominator_x == 0.0 or denominator_y == 0.0:
        return 0.0
    return numerator / (denominator_x * denominator_y)
