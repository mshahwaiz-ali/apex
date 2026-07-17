"""Tests for complete isolated final-test calibration diagnostics."""

from __future__ import annotations

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)
from apex.optimization.empirical import (
    S10_EMPIRICAL_REPORT_SCHEMA_VERSION,
    build_empirical_calibration_report,
)


def _summary(
    *,
    expectancy: float,
    net_profit: float,
    drawdown: float,
) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=20,
        win_rate=0.60,
        expectancy=expectancy,
        profit_factor=1.50,
        maximum_drawdown=drawdown,
        net_profit=net_profit,
        by_symbol={"BTCUSDT": 10, "ETHUSDT": 10},
        by_strategy={"trend_pullback": 20},
        by_regime={"trend": 12, "range": 8},
        by_score_band={"70-79": 8, "80-89": 12},
        loss_rate=0.35,
        average_win=3.0,
        average_loss=-1.5,
    )


def test_final_test_audit_preserves_complete_comparison_diagnostics() -> None:
    split = WalkForwardSplit(
        train_start="2025-01-01",
        train_end="2025-06-30",
        validation_start="2025-07-01",
        validation_end="2025-09-30",
        out_of_sample_start="2025-10-01",
        out_of_sample_end="2025-12-31",
    )
    run_config = OptimizationRunConfig(
        identifier="final-test-diagnostics",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.05,
        split=split,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 72},
    )

    report = build_empirical_calibration_report(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_baseline=_summary(expectancy=0.20, net_profit=4.0, drawdown=0.12),
        train_candidate=_summary(expectancy=0.30, net_profit=6.0, drawdown=0.10),
        validation_baseline=_summary(expectancy=0.15, net_profit=3.0, drawdown=0.11),
        validation_candidate=_summary(expectancy=0.25, net_profit=5.0, drawdown=0.09),
        final_test_baseline=_summary(expectancy=0.10, net_profit=2.0, drawdown=0.13),
        final_test_candidate=_summary(expectancy=0.18, net_profit=3.6, drawdown=0.11),
    )

    audit = report.payload["final_test_audit"]
    comparison = audit["comparison"]

    assert report.payload["schema_version"] == S10_EMPIRICAL_REPORT_SCHEMA_VERSION
    assert S10_EMPIRICAL_REPORT_SCHEMA_VERSION == 2
    assert audit["used_for_selection"] is False
    assert comparison["decision"] == audit["decision"]
    assert comparison["reasons"] == audit["reasons"]
    assert comparison["performance_deltas"]["expectancy"] == 0.08
    assert comparison["performance_deltas"]["net_profit"] == 1.6
    assert comparison["performance_deltas"]["maximum_drawdown"] == -0.02


def test_unselected_candidate_does_not_run_final_test_comparison() -> None:
    split = WalkForwardSplit(
        train_start="2025-01-01",
        train_end="2025-06-30",
        validation_start="2025-07-01",
        validation_end="2025-09-30",
        out_of_sample_start="2025-10-01",
        out_of_sample_end="2025-12-31",
    )
    run_config = OptimizationRunConfig(
        identifier="rejected-final-test-diagnostics",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.50,
        split=split,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 72},
    )

    report = build_empirical_calibration_report(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_baseline=_summary(expectancy=0.20, net_profit=4.0, drawdown=0.12),
        train_candidate=_summary(expectancy=0.30, net_profit=6.0, drawdown=0.10),
        validation_baseline=_summary(expectancy=0.15, net_profit=3.0, drawdown=0.11),
        validation_candidate=_summary(expectancy=0.25, net_profit=5.0, drawdown=0.09),
        final_test_baseline=_summary(expectancy=0.10, net_profit=2.0, drawdown=0.13),
        final_test_candidate=_summary(expectancy=0.18, net_profit=3.6, drawdown=0.11),
    )

    assert report.payload["selected_for_final_test_audit"] is False
    assert report.payload["final_test_audit"] is None
