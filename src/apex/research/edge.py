"""Expected-value computation and immutable model-promotion gates."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpectedRInputs:
    fill_probability: float
    outcome_probabilities: tuple[tuple[str, float], ...]
    outcome_r: tuple[tuple[str, float], ...]
    expected_cost_r: float

    def calculate(self) -> float:
        probabilities = dict(self.outcome_probabilities)
        outcomes = dict(self.outcome_r)
        if not 0 <= self.fill_probability <= 1:
            raise ValueError("fill probability must be between zero and one")
        if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6):
            raise ValueError("conditional outcome probabilities must sum to one")
        if probabilities.keys() != outcomes.keys():
            raise ValueError("outcome probability and R keys must match")
        conditional_r = sum(probabilities[key] * outcomes[key] for key in probabilities)
        return self.fill_probability * conditional_r - self.expected_cost_r


@dataclass(frozen=True, slots=True)
class PromotionMetrics:
    executed_outcomes: int
    segment_outcomes: int
    net_expectancy_r: float
    brier_skill: float
    calibration_error: float
    deflated_sharpe_probability: float
    probability_backtest_overfitting: float
    leakage_checks_passed: bool
    stability_checks_passed: bool
    artifact_integrity_passed: bool


@dataclass(frozen=True, slots=True)
class EdgePromotionDecision:
    promoted: bool
    failed_gates: tuple[str, ...]


def evaluate_promotion(
    metrics: PromotionMetrics, *, separately_published_segment: bool = False
) -> EdgePromotionDecision:
    failed: list[str] = []
    if metrics.executed_outcomes < 200:
        failed.append("fewer than 200 final-test executed outcomes")
    if separately_published_segment and metrics.segment_outcomes < 50:
        failed.append("fewer than 50 final-test segment outcomes")
    if metrics.net_expectancy_r <= 0:
        failed.append("non-positive final-test expectancy after costs")
    if metrics.brier_skill <= 0:
        failed.append("Brier skill does not beat base rate")
    if metrics.calibration_error > 0.05:
        failed.append("calibration error exceeds 0.05")
    if metrics.deflated_sharpe_probability < 0.95:
        failed.append("deflated-Sharpe probability below 0.95")
    if metrics.probability_backtest_overfitting > 0.20:
        failed.append("PBO exceeds 0.20")
    if not metrics.leakage_checks_passed:
        failed.append("leakage checks failed")
    if not metrics.stability_checks_passed:
        failed.append("stability checks failed")
    if not metrics.artifact_integrity_passed:
        failed.append("artifact integrity failed")
    return EdgePromotionDecision(promoted=not failed, failed_gates=tuple(failed))


__all__ = [
    "EdgePromotionDecision",
    "ExpectedRInputs",
    "PromotionMetrics",
    "evaluate_promotion",
]
