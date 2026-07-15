from __future__ import annotations

from apex.optimization import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
    build_empirical_calibration_report,
)


def _summary(expectancy: float, *, trades: int = 20) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=trades,
        win_rate=0.55,
        expectancy=expectancy,
        profit_factor=1.4,
        maximum_drawdown=0.10,
        net_profit=expectancy * trades,
        by_symbol={"BTCUSDT": trades // 2, "ETHUSDT": trades - trades // 2},
        by_strategy={"trend_pullback": trades},
        by_regime={"risk_on": trades},
        by_score_band={"80-89": trades},
    )


def _inputs() -> tuple[WalkForwardSplit, OptimizationRunConfig, CandidateParameterSet]:
    split = WalkForwardSplit(
        train_start="2025-01-01",
        train_end="2025-06-30",
        validation_start="2025-07-01",
        validation_end="2025-09-30",
        out_of_sample_start="2025-10-01",
        out_of_sample_end="2025-12-31",
    )
    config = OptimizationRunConfig(
        identifier="s10-rejections",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.05,
        split=split,
    )
    candidate = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 78},
    )
    return split, config, candidate


def test_weak_validation_prevents_final_test_audit() -> None:
    split, config, candidate = _inputs()
    report = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=candidate,
        train_baseline=_summary(0.10),
        train_candidate=_summary(0.20),
        validation_baseline=_summary(0.15),
        validation_candidate=_summary(0.16),
        final_test_baseline=_summary(0.10),
        final_test_candidate=_summary(0.30),
    )

    assert report.payload["selection"]["decision"] == "rejected"
    assert report.payload["selected_for_final_test_audit"] is False
    assert report.payload["final_test_audit"] is None


def test_failed_final_test_is_recorded_without_reversing_selection() -> None:
    split, config, candidate = _inputs()
    report = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=candidate,
        train_baseline=_summary(0.10),
        train_candidate=_summary(0.20),
        validation_baseline=_summary(0.10),
        validation_candidate=_summary(0.20),
        final_test_baseline=_summary(0.20),
        final_test_candidate=_summary(0.10),
    )

    assert report.payload["selected_for_final_test_audit"] is True
    assert report.payload["final_test_audit"]["decision"] == "rejected"
    assert report.payload["final_test_audit"]["used_for_selection"] is False


def test_selected_candidate_without_final_test_remains_explicitly_unaudited() -> None:
    split, config, candidate = _inputs()
    report = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=candidate,
        train_baseline=_summary(0.10),
        train_candidate=_summary(0.20),
        validation_baseline=_summary(0.10),
        validation_candidate=_summary(0.20),
    )

    assert report.payload["selected_for_final_test_audit"] is True
    assert report.payload["final_test_audit"] is None
