from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.research.payoff import (
    PayoffExperiment,
    PayoffObservation,
    attempted_payoff_configurations,
    evaluate_payoff_shadows,
)
from apex.research.precision import (
    evaluate_paper_precision_promotion,
    evaluate_precision_promotion,
    precision_frontier,
    select_validation_threshold,
)
from apex.research.splits import grouped_chronological_split


def test_grouped_split_never_separates_one_decision_group() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    timestamps = tuple(start + timedelta(days=index // 2) for index in range(20))
    groups = tuple(f"group-{index // 2}" for index in range(20))

    split = grouped_chronological_split(timestamps, groups)
    partitions = (set(split.training), set(split.calibration), set(split.final_test))

    for group in set(groups):
        indexes = {index for index, value in enumerate(groups) if value == group}
        assert sum(bool(indexes & partition) for partition in partitions) <= 1


def test_precision_threshold_uses_profitability_not_accuracy_alone() -> None:
    probabilities = (0.95, 0.90, 0.85, 0.80, 0.70, 0.60)
    returns = (0.3, 0.3, -1.0, 0.4, 0.4, -1.0)

    frontier = precision_frontier(
        probabilities,
        returns,
        thresholds=(0.70, 0.85, 0.90),
        minimum_outcomes=2,
    )
    selected = select_validation_threshold(frontier)

    assert selected is not None
    assert selected.threshold == 0.90
    assert selected.expectancy_r > 0.0
    assert selected.profit_factor >= 1.20


def test_historical_promotion_fails_closed_when_pbo_is_unavailable() -> None:
    result = evaluate_precision_promotion(
        [0.5] * 200,
        folds_positive=True,
        exclusions_positive=True,
        stable_cohorts=4,
        drawdown_within_budget=True,
        brier_skill=0.1,
        calibration_error=0.01,
        dsr_probability=0.99,
        pbo_probability=None,
    )

    assert result.promoted is False
    assert "PBO is unavailable" in result.failed_gates


def test_paper_gate_enforces_time_symbol_and_cohort_diversity() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    outcomes = [
        (start + timedelta(days=index), "BTCUSDT", "high_liquidity", 0.5) for index in range(50)
    ]

    result = evaluate_paper_precision_promotion(outcomes)

    assert result.promoted is False
    assert "paper observation period is shorter than eight weeks" in result.failed_gates
    assert "fewer than eight paper symbols" in result.failed_gates
    assert "fewer than four paper cohorts" in result.failed_gates


def test_payoff_experiments_are_shadow_only_and_counted() -> None:
    results = evaluate_payoff_shadows(
        PayoffObservation(
            candidate_id="candidate-1",
            canonical_net_r=0.4,
            tp1_net_r=0.5,
            runner_net_r=1.2,
            confirmation_or_retest_filled=True,
            chased=False,
            higher_cost_delta_r=0.2,
            delayed_fill_delta_r=0.1,
        )
    )

    assert attempted_payoff_configurations(results) == len(PayoffExperiment)
    assert all(result.authority == "shadow_only" for result in results)
    assert (
        next(
            result for result in results if result.experiment is PayoffExperiment.HIGHER_COST_STRESS
        ).net_r
        == 0.2
    )
