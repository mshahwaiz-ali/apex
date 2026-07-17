"""Tests for entry-actionability calibration stability gates."""

from __future__ import annotations

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)
from apex.optimization.empirical import (
    StabilityPolicy,
    build_empirical_calibration_report,
)


def _split() -> WalkForwardSplit:
    return WalkForwardSplit(
        train_start="2025-01-01",
        train_end="2025-06-30",
        validation_start="2025-07-01",
        validation_end="2025-09-30",
        out_of_sample_start="2025-10-01",
        out_of_sample_end="2025-12-31",
    )


def _summary(
    *,
    expectancy: float,
    by_entry_actionability: dict[str, int] | None = None,
) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=20,
        win_rate=0.60,
        expectancy=expectancy,
        profit_factor=1.50,
        maximum_drawdown=0.10,
        net_profit=expectancy * 20,
        by_symbol={"BTCUSDT": 10, "ETHUSDT": 10},
        by_strategy={"trend_pullback": 20},
        by_regime={"trend": 12, "range": 8},
        by_score_band={"70-79": 8, "80-89": 12},
        by_entry_actionability=by_entry_actionability or {},
    )


def _report(
    *,
    validation_actionability: dict[str, int] | None,
    policy: StabilityPolicy,
):
    split = _split()
    config = OptimizationRunConfig(
        identifier="entry-actionability-stability",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.05,
        split=split,
    )
    parameters = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 70},
    )
    return build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20),
        train_candidate=_summary(expectancy=0.30),
        validation_baseline=_summary(expectancy=0.15),
        validation_candidate=_summary(
            expectancy=0.25,
            by_entry_actionability=validation_actionability,
        ),
        stability_policy=policy,
    )


def test_missing_actionability_distribution_is_backward_compatible_by_default() -> None:
    report = _report(
        validation_actionability=None,
        policy=StabilityPolicy(),
    )

    assert report.payload["stability"]["passed"] is True
    assert "entry_actionabilities" not in report.payload["stability"]["distributions"]


def test_required_actionability_distribution_rejects_missing_data() -> None:
    report = _report(
        validation_actionability=None,
        policy=StabilityPolicy(require_entry_actionability_distribution=True),
    )

    assert report.payload["stability"]["passed"] is False
    assert report.payload["selected_for_final_test_audit"] is False
    assert "candidate does not cover enough entry actionabilities" in report.payload[
        "stability"
    ]["reasons"]


def test_actionability_concentration_rejects_candidate() -> None:
    report = _report(
        validation_actionability={"READY": 19, "AGGRESSIVE": 1},
        policy=StabilityPolicy(
            require_entry_actionability_distribution=True,
            minimum_entry_actionabilities=2,
            maximum_entry_actionability_trade_share=0.80,
        ),
    )

    distribution = report.payload["stability"]["distributions"]["entry_actionabilities"]
    assert distribution["group_count"] == 2
    assert distribution["largest_trade_share"] == 0.95
    assert report.payload["stability"]["passed"] is False
    assert "candidate is too concentrated in one entry actionabilities group" in report.payload[
        "stability"
    ]["reasons"]


def test_balanced_actionability_distribution_passes() -> None:
    report = _report(
        validation_actionability={"READY": 10, "AGGRESSIVE": 6, "PULLBACK_PREFERRED": 4},
        policy=StabilityPolicy(
            require_entry_actionability_distribution=True,
            minimum_entry_actionabilities=2,
            maximum_entry_actionability_trade_share=0.70,
        ),
    )

    assert report.payload["stability"]["passed"] is True
    assert report.payload["selected_for_final_test_audit"] is True
