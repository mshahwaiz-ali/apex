"""Tests for untouched final-test evaluation and calibration persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from apex.calibration import (
    CalibrationCandidate,
    CalibrationDecision,
    CalibrationMetrics,
    CalibrationPolicy,
    CalibrationReason,
    WalkForwardCalibrationReport,
    attach_final_test_results,
    load_calibration_report_payload,
    load_calibration_report_sqlite,
    select_calibration_candidates,
    write_calibration_report,
    write_calibration_report_sqlite,
)


def _metrics(expectancy: float, drawdown: float, sample_size: int = 100) -> CalibrationMetrics:
    return CalibrationMetrics(
        sample_size=sample_size,
        expectancy=expectancy,
        maximum_drawdown_r=drawdown,
        expectancy_by_symbol={"BTCUSDT": expectancy, "ETHUSDT": expectancy},
        expectancy_by_regime={"trend": expectancy, "range": expectancy},
    )


def _selected_report() -> WalkForwardCalibrationReport:
    candidate = CalibrationCandidate(
        identifier="candidate-a",
        strategy="trend_pullback",
        parameter_changes={"minimum_score": 78},
        baseline_train=_metrics(0.30, 8.0, 150),
        candidate_train=_metrics(0.40, 7.0, 150),
        baseline_validation=_metrics(0.30, 8.0, 80),
        candidate_validation=_metrics(0.45, 7.0, 80),
    )
    return select_calibration_candidates(
        (candidate,),
        policy=CalibrationPolicy(
            minimum_train_trades=100,
            minimum_validation_trades=50,
            minimum_stable_symbols=2,
            minimum_stable_regimes=2,
        ),
    )


def test_final_test_accepts_preselected_stable_candidate() -> None:
    report = _selected_report()
    completed = attach_final_test_results(
        report,
        baseline_metrics_by_candidate={"candidate-a": _metrics(0.30, 8.0)},
        candidate_metrics_by_candidate={"candidate-a": _metrics(0.35, 7.0)},
        validation_expectancy_by_candidate={"candidate-a": 0.45},
    )

    result = completed.final_test_assessments[0]
    assert result.decision is CalibrationDecision.ACCEPT
    assert result.reasons == (CalibrationReason.CHANGE_ACCEPTED,)
    assert completed.selected_candidate_ids == report.selected_candidate_ids


def test_final_test_rejects_degraded_candidate_without_changing_preselection() -> None:
    report = _selected_report()
    completed = attach_final_test_results(
        report,
        baseline_metrics_by_candidate={"candidate-a": _metrics(0.30, 8.0)},
        candidate_metrics_by_candidate={"candidate-a": _metrics(0.05, 9.0)},
        validation_expectancy_by_candidate={"candidate-a": 0.45},
    )

    result = completed.final_test_assessments[0]
    assert result.decision is CalibrationDecision.REJECT
    assert result.reasons == (CalibrationReason.FINAL_TEST_DEGRADED,)
    assert completed.selected_candidate_ids == ("candidate-a",)


def test_final_test_cannot_add_unselected_candidate() -> None:
    report = _selected_report()
    with pytest.raises(ValueError, match="cover selected candidates exactly"):
        attach_final_test_results(
            report,
            baseline_metrics_by_candidate={"candidate-a": _metrics(0.30, 8.0)},
            candidate_metrics_by_candidate={
                "candidate-a": _metrics(0.35, 7.0),
                "candidate-b": _metrics(0.50, 6.0),
            },
            validation_expectancy_by_candidate={"candidate-a": 0.45},
        )


def test_json_and_sqlite_round_trip(tmp_path: Path) -> None:
    report = _selected_report()
    json_path = tmp_path / "calibration.json"
    db_path = tmp_path / "calibration.sqlite3"

    write_calibration_report(json_path, report)
    write_calibration_report_sqlite(db_path, report)

    json_payload = load_calibration_report_payload(json_path)
    db_payload = load_calibration_report_sqlite(db_path, report.report_id)
    assert json_payload["report_id"] == report.report_id
    assert db_payload["selected_candidate_ids"] == ["candidate-a"]


def test_json_overwrite_requires_force(tmp_path: Path) -> None:
    report = _selected_report()
    path = tmp_path / "calibration.json"
    write_calibration_report(path, report)

    with pytest.raises(ValueError, match="already exists"):
        write_calibration_report(path, report)
    write_calibration_report(path, report, force=True)
