"""Tests for empirical calibration report write-time integrity."""

from __future__ import annotations

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
    EmpiricalCalibrationReport,
    build_empirical_calibration_report,
    write_empirical_calibration_report,
)


def _summary(*, expectancy: float) -> PerformanceSummary:
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
    )


def _report() -> EmpiricalCalibrationReport:
    split = WalkForwardSplit(
        train_start="2025-01-01",
        train_end="2025-06-30",
        validation_start="2025-07-01",
        validation_end="2025-09-30",
        out_of_sample_start="2025-10-01",
        out_of_sample_end="2025-12-31",
    )
    config = OptimizationRunConfig(
        identifier="write-integrity",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        minimum_trades=10,
        minimum_expectancy_delta=0.05,
        split=split,
    )
    parameters = CandidateParameterSet(
        identifier="candidate-a",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 72},
    )
    return build_empirical_calibration_report(
        split=split,
        run_config=config,
        parameter_set=parameters,
        train_baseline=_summary(expectancy=0.20),
        train_candidate=_summary(expectancy=0.30),
        validation_baseline=_summary(expectancy=0.15),
        validation_candidate=_summary(expectancy=0.25),
    )


def test_valid_report_writes_normally(tmp_path: Path) -> None:
    report = _report()
    path = tmp_path / "report.json"

    write_empirical_calibration_report(report, path)

    assert path.is_file()


def test_mutated_payload_is_rejected_before_write(tmp_path: Path) -> None:
    report = _report()
    report.payload["selected_for_final_test_audit"] = False
    path = tmp_path / "mutated.json"

    with pytest.raises(ValueError, match="hash does not match"):
        write_empirical_calibration_report(report, path)

    assert not path.exists()


def test_mismatched_report_hash_attribute_is_rejected(tmp_path: Path) -> None:
    valid = _report()
    report = EmpiricalCalibrationReport(
        payload=dict(valid.payload),
        report_sha256="0" * 64,
    )
    path = tmp_path / "mismatched.json"

    with pytest.raises(ValueError, match="hash attribute"):
        write_empirical_calibration_report(report, path)

    assert not path.exists()


def test_missing_embedded_hash_is_rejected(tmp_path: Path) -> None:
    valid = _report()
    payload = dict(valid.payload)
    payload.pop("report_sha256")
    report = EmpiricalCalibrationReport(
        payload=payload,
        report_sha256=valid.report_sha256,
    )
    path = tmp_path / "missing-hash.json"

    with pytest.raises(ValueError, match="embedded hash"):
        write_empirical_calibration_report(report, path)

    assert not path.exists()
