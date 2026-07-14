"""Tests for baseline JSON and SQLite persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from apex.baseline import (
    BaselineEvaluationReport,
    BaselineReason,
    BaselineVerdict,
    CostSensitivityResult,
    StrategyBaselineAssessment,
    list_baseline_report_metadata_sqlite,
    load_baseline_report_payload,
    load_baseline_report_sqlite,
    write_baseline_report,
    write_baseline_report_sqlite,
)


def _report() -> BaselineEvaluationReport:
    assessment = StrategyBaselineAssessment(
        strategy="trend_pullback",
        verdict=BaselineVerdict.ACCEPT,
        sample_size=120,
        expectancy=0.35,
        profit_factor=1.4,
        maximum_drawdown_r=6.0,
        symbols=("BTCUSDT", "ETHUSDT"),
        regimes=("range", "trend"),
        score_bands={"70_79": 0.2, "80_89": 0.5},
        cost_sensitivity=(
            CostSensitivityResult(
                scenario_id="base",
                expectancy=0.35,
                degradation_from_baseline=0.0,
                stable=True,
            ),
        ),
        reasons=(BaselineReason.BASELINE_ACCEPTED,),
    )
    return BaselineEvaluationReport(
        plan_id="plan-1",
        baseline_scenario_id="base",
        scenario_ids=("base",),
        assessments=(assessment,),
        report_id="report-1",
    )


def test_json_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    report = _report()

    write_baseline_report(path, report)
    payload = load_baseline_report_payload(path)

    assert payload["report_id"] == report.report_id
    assert payload["plan_id"] == report.plan_id
    with pytest.raises(ValueError, match="already exists"):
        write_baseline_report(path, report)
    write_baseline_report(path, report, force=True)


def test_sqlite_upsert_load_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "baseline.sqlite3"
    report = _report()

    write_baseline_report_sqlite(path, report)
    write_baseline_report_sqlite(path, report)
    payload = load_baseline_report_sqlite(path, report.report_id)
    metadata = list_baseline_report_metadata_sqlite(path)

    assert payload["report_id"] == report.report_id
    assert metadata == ({"report_id": "report-1", "plan_id": "plan-1"},)


def test_missing_sqlite_report_raises_key_error(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_baseline_report_sqlite(tmp_path / "empty.sqlite3", "missing")
