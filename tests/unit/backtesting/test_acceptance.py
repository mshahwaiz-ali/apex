from __future__ import annotations

from apex.backtesting.acceptance import (
    CalibrationMetric,
    calibration_acceptance_payload,
    evaluate_calibration_acceptance,
)


def _complete_metrics(*, expectancy: float = 0.25) -> dict[str, float]:
    return {
        metric.value: expectancy if metric is CalibrationMetric.EXPECTANCY else 0.5
        for metric in CalibrationMetric
    }


def test_acceptance_fails_closed_when_metrics_are_incomplete() -> None:
    report = evaluate_calibration_acceptance(
        {
            "win_rate": 0.6,
            "expectancy": 0.2,
        },
        sample_size=20,
        acceptable_drawdown=True,
        stable_regime_performance=True,
    )

    assert report.confidence_claims_allowed is False
    assert CalibrationMetric.WIN_RATE in report.available_metrics
    assert CalibrationMetric.PROFIT_FACTOR in report.missing_metrics
    assert report.blockers == ("required_metrics_incomplete",)


def test_acceptance_rejects_high_hit_rate_with_negative_expectancy() -> None:
    metrics = _complete_metrics(expectancy=-0.1)
    metrics["tp1_hit_rate"] = 0.9

    report = evaluate_calibration_acceptance(
        metrics,
        sample_size=100,
        acceptable_drawdown=True,
        stable_regime_performance=True,
    )

    assert report.positive_expectancy is False
    assert report.confidence_claims_allowed is False
    assert report.blockers == ("expectancy_not_positive",)


def test_acceptance_allows_claims_only_when_every_gate_passes() -> None:
    report = evaluate_calibration_acceptance(
        _complete_metrics(),
        sample_size=250,
        acceptable_drawdown=True,
        stable_regime_performance=True,
    )
    payload = calibration_acceptance_payload(report)

    assert report.missing_metrics == ()
    assert report.confidence_claims_allowed is True
    assert report.blockers == ()
    assert payload["confidence_claims_allowed"] is True
    assert payload["sample_size"] == 250
    assert payload["acceptance_principle"] == (
        "calibrated precision + positive expectancy + tolerable drawdown + "
        "stable regime performance"
    )


def test_sample_size_is_always_required() -> None:
    report = evaluate_calibration_acceptance(
        _complete_metrics(),
        sample_size=0,
        acceptable_drawdown=True,
        stable_regime_performance=True,
    )

    assert report.confidence_claims_allowed is False
    assert report.blockers == ("sample_size_unavailable",)
