from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    load_and_verify_empirical_calibration_report,
    write_empirical_calibration_report,
)


def _summary(
    *,
    expectancy: float,
    drawdown: float,
    trades: int = 20,
    by_symbol: dict[str, int] | None = None,
) -> PerformanceSummary:
    return PerformanceSummary(
        total_trades=trades,
        win_rate=0.60,
        expectancy=expectancy,
        profit_factor=1.50,
        maximum_drawdown=drawdown,
        net_profit=expectancy * trades,
        by_symbol=by_symbol or {"BTCUSDT": 10, "ETHUSDT": 10},
        by_strategy={"trend_pullback": trades},
        by_regime={"risk_on": 12, "range": 8},
        by_score_band={"70-79": 8, "80-89": 12},
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
        identifier="s10-fixture",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.05,
        maximum_drawdown_increase_pct=0.0,
        split=split,
    )
    parameters = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"trend_pullback_minimum_score": 76},
    )
    return split, config, parameters


def test_empirical_report_is_deterministic_and_keeps_final_test_out_of_selection(
    tmp_path: Path,
) -> None:
    split, config, parameters = _inputs()
    first = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20, drawdown=0.10),
        train_candidate=_summary(expectancy=0.30, drawdown=0.09),
        validation_baseline=_summary(expectancy=0.15, drawdown=0.12),
        validation_candidate=_summary(expectancy=0.25, drawdown=0.10),
        final_test_baseline=_summary(expectancy=0.10, drawdown=0.11),
        final_test_candidate=_summary(expectancy=0.18, drawdown=0.10),
    )
    second = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20, drawdown=0.10),
        train_candidate=_summary(expectancy=0.30, drawdown=0.09),
        validation_baseline=_summary(expectancy=0.15, drawdown=0.12),
        validation_candidate=_summary(expectancy=0.25, drawdown=0.10),
        final_test_baseline=_summary(expectancy=0.10, drawdown=0.11),
        final_test_candidate=_summary(expectancy=0.18, drawdown=0.10),
    )

    assert first == second
    assert first.payload["selected_for_final_test_audit"] is True
    assert first.payload["final_test_audit"]["used_for_selection"] is False

    path = tmp_path / "report.json"
    write_empirical_calibration_report(first, path)
    assert load_and_verify_empirical_calibration_report(path) == first


def test_stability_rejects_single_symbol_dependency() -> None:
    split, config, parameters = _inputs()
    report = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20, drawdown=0.10),
        train_candidate=_summary(expectancy=0.30, drawdown=0.09),
        validation_baseline=_summary(expectancy=0.15, drawdown=0.12),
        validation_candidate=_summary(
            expectancy=0.25,
            drawdown=0.10,
            by_symbol={"BTCUSDT": 20},
        ),
        stability_policy=StabilityPolicy(minimum_symbols=2),
    )

    assert report.payload["stability"]["passed"] is False
    assert report.payload["selected_for_final_test_audit"] is False
    assert report.payload["final_test_audit"] is None


def test_tampered_report_is_rejected(tmp_path: Path) -> None:
    split, config, parameters = _inputs()
    report = build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20, drawdown=0.10),
        train_candidate=_summary(expectancy=0.30, drawdown=0.09),
        validation_baseline=_summary(expectancy=0.15, drawdown=0.12),
        validation_candidate=_summary(expectancy=0.25, drawdown=0.10),
    )
    path = tmp_path / "report.json"
    write_empirical_calibration_report(report, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["selected_for_final_test_audit"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_empirical_calibration_report(path)
