from apex.backtesting import (
    CalibrationEvidenceCoverage,
    build_calibration_evidence_coverage,
    calibration_evidence_coverage_payload,
)
from apex.backtesting.acceptance import CalibrationMetric


def test_coverage_reports_required_available_and_missing_metrics() -> None:
    available = {
        CalibrationMetric.WIN_RATE.value,
        CalibrationMetric.PROFIT_FACTOR.value,
        CalibrationMetric.EXPECTANCY.value,
    }

    report = build_calibration_evidence_coverage(available)
    payload = calibration_evidence_coverage_payload(report)

    assert report.complete is False
    assert report.available_metrics == (
        CalibrationMetric.WIN_RATE,
        CalibrationMetric.PROFIT_FACTOR,
        CalibrationMetric.EXPECTANCY,
    )
    assert CalibrationMetric.RUNNER_SUCCESS_RATE in report.missing_metrics
    assert payload["calibration_authoritative"] is False


def test_coverage_is_complete_only_when_every_required_metric_exists() -> None:
    report = build_calibration_evidence_coverage(
        frozenset(metric.value for metric in CalibrationMetric)
    )

    assert report.complete is True
    assert report.missing_metrics == ()
    assert report.calibration_authoritative is False


def test_coverage_payload_explains_current_unsupported_metrics() -> None:
    report = build_calibration_evidence_coverage(set())
    payload = calibration_evidence_coverage_payload(report)
    reasons = payload["missing_metric_reasons"]

    assert isinstance(reasons, dict)
    assert CalibrationMetric.RUNNER_SUCCESS_RATE.value in reasons
    assert CalibrationMetric.FALSE_CMP_SIGNAL_RATE.value in reasons
    assert CalibrationMetric.FEES_AND_SLIPPAGE.value in reasons
    assert CalibrationMetric.LIQUIDATION_OR_MARGIN_FAILURE_RATE.value in reasons


def test_coverage_contract_rejects_overlapping_evidence() -> None:
    try:
        CalibrationEvidenceCoverage(
            required_metrics=(CalibrationMetric.WIN_RATE,),
            available_metrics=(CalibrationMetric.WIN_RATE,),
            missing_metrics=(CalibrationMetric.WIN_RATE,),
            complete=False,
        )
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping evidence should be rejected")
