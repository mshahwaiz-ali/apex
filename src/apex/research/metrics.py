"""Calibration and overfitting diagnostics without trading-library dependencies."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import fmean, pstdev


def brier_score(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("Brier score requires equal non-empty inputs")
    return fmean(
        (float(label) - probability) ** 2
        for label, probability in zip(labels, probabilities, strict=True)
    )


def expected_calibration_error(
    labels: Sequence[int], probabilities: Sequence[float], *, bins: int = 10
) -> float:
    if bins < 2 or not labels or len(labels) != len(probabilities):
        raise ValueError("calibration error requires equal non-empty inputs and at least two bins")
    total = len(labels)
    error = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = tuple(
            position
            for position, probability in enumerate(probabilities)
            if lower <= probability < upper or (index == bins - 1 and probability == 1.0)
        )
        if not selected:
            continue
        confidence = fmean(probabilities[position] for position in selected)
        frequency = fmean(labels[position] for position in selected)
        error += len(selected) / total * abs(confidence - frequency)
    return error


def brier_skill_score(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    base_rate = fmean(labels)
    baseline = brier_score(labels, [base_rate] * len(labels))
    score = brier_score(labels, probabilities)
    return 1.0 - score / baseline if baseline > 0 else 0.0


def deflated_sharpe_probability(returns: Sequence[float], *, trials: int = 1) -> float:
    """Conservative normal approximation to the probability Sharpe exceeds trial bias."""

    if len(returns) < 3 or trials < 1:
        return 0.0
    deviation = pstdev(returns)
    if deviation <= 0:
        return 1.0 if fmean(returns) > 0 else 0.0
    observed = fmean(returns) / deviation
    expected_max = math.sqrt(2.0 * math.log(max(2, trials))) / math.sqrt(len(returns))
    standard_error = math.sqrt((1.0 + 0.5 * observed**2) / (len(returns) - 1))
    z_score = (observed - expected_max) / max(standard_error, 1e-12)
    return 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))


def probability_of_backtest_overfitting(
    train_scores: Sequence[float], test_scores: Sequence[float]
) -> float:
    """Estimate PBO as the share of train winners below the test median."""

    if not train_scores or len(train_scores) != len(test_scores):
        raise ValueError("PBO requires equal non-empty strategy score vectors")
    winner = max(range(len(train_scores)), key=lambda index: (train_scores[index], -index))
    ordered_test = sorted(test_scores)
    midpoint = ordered_test[len(ordered_test) // 2]
    if len(train_scores) == 1:
        return 0.0 if test_scores[winner] > 0 else 1.0
    below = sum(
        1
        for index in range(len(train_scores))
        if train_scores[index] >= train_scores[winner] and test_scores[index] <= midpoint
    )
    return below / max(1, sum(score >= train_scores[winner] for score in train_scores))


__all__ = [
    "brier_score",
    "brier_skill_score",
    "deflated_sharpe_probability",
    "expected_calibration_error",
    "probability_of_backtest_overfitting",
]
