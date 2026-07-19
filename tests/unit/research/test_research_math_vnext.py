from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.research.edge import ExpectedRInputs, PromotionMetrics, evaluate_promotion
from apex.research.metrics import brier_skill_score, expected_calibration_error
from apex.research.splits import chronological_split


def test_expected_r_includes_fill_probability_and_costs() -> None:
    inputs = ExpectedRInputs(
        fill_probability=0.5,
        outcome_probabilities=(("target", 0.6), ("stop", 0.4)),
        outcome_r=(("target", 2.0), ("stop", -1.0)),
        expected_cost_r=0.1,
    )
    assert inputs.calculate() == pytest.approx(0.3)


def test_chronological_split_purges_boundary_overlap() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    timestamps = tuple(start + timedelta(hours=index) for index in range(20))
    split = chronological_split(timestamps, horizon=timedelta(hours=2), embargo=timedelta(hours=1))
    assert set(split.training).isdisjoint(split.calibration)
    assert set(split.calibration).isdisjoint(split.final_test)
    assert split.purged


def test_promotion_gates_are_not_loosened() -> None:
    failed = evaluate_promotion(
        PromotionMetrics(199, 49, 0.1, 0.01, 0.04, 0.96, 0.19, True, True, True),
        separately_published_segment=True,
    )
    assert failed.promoted is False
    assert len(failed.failed_gates) == 2


def test_calibration_metrics_reward_informative_probabilities() -> None:
    labels = [0, 0, 1, 1]
    probabilities = [0.05, 0.20, 0.80, 0.95]
    assert brier_skill_score(labels, probabilities) > 0
    assert expected_calibration_error(labels, probabilities, bins=2) <= 0.2
