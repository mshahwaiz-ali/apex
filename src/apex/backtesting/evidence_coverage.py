"""Evidence coverage reporting for calibration acceptance metrics."""

from __future__ import annotations

from dataclasses import dataclass

from apex.backtesting.acceptance import CalibrationMetric


@dataclass(frozen=True, slots=True)
class CalibrationEvidenceCoverage:
    """Describe required, available, and missing calibration evidence."""

    required_metrics: tuple[CalibrationMetric, ...]
    available_metrics: tuple[CalibrationMetric, ...]
    missing_metrics: tuple[CalibrationMetric, ...]
    complete: bool
    calibration_authoritative: bool = False

    def __post_init__(self) -> None:
        if self.calibration_authoritative:
            raise ValueError("evidence coverage cannot grant calibration authority")
        required = set(self.required_metrics)
        available = set(self.available_metrics)
        missing = set(self.missing_metrics)
        if available | missing != required:
            raise ValueError("available and missing metrics must cover required metrics")
        if available & missing:
            raise ValueError("available and missing metrics must not overlap")
        if self.complete is not (not self.missing_metrics):
            raise ValueError("coverage completeness must match missing metrics")


def build_calibration_evidence_coverage(
    available_metric_names: set[str] | frozenset[str],
) -> CalibrationEvidenceCoverage:
    """Build deterministic coverage from metric names already reported."""

    required = tuple(CalibrationMetric)
    available = tuple(metric for metric in required if metric.value in available_metric_names)
    missing = tuple(metric for metric in required if metric not in available)
    return CalibrationEvidenceCoverage(
        required_metrics=required,
        available_metrics=available,
        missing_metrics=missing,
        complete=not missing,
    )


def calibration_evidence_coverage_payload(
    report: CalibrationEvidenceCoverage,
) -> dict[str, object]:
    return {
        "required_metrics": [metric.value for metric in report.required_metrics],
        "available_metrics": [metric.value for metric in report.available_metrics],
        "missing_metrics": [metric.value for metric in report.missing_metrics],
        "complete": report.complete,
        "calibration_authoritative": report.calibration_authoritative,
        "missing_metric_reasons": {
            CalibrationMetric.RUNNER_SUCCESS_RATE.value: (
                "runner lifecycle success is not yet represented in BacktestReport"
            ),
            CalibrationMetric.FALSE_CMP_SIGNAL_RATE.value: (
                "false CMP signal classification is not yet represented in BacktestReport"
            ),
            CalibrationMetric.FEES_AND_SLIPPAGE.value: (
                "fees and slippage are not yet exposed as one calibration metric"
            ),
            CalibrationMetric.LIQUIDATION_OR_MARGIN_FAILURE_RATE.value: (
                "liquidation and margin failure are not simulated by the current backtest"
            ),
        },
    }


__all__ = [
    "CalibrationEvidenceCoverage",
    "build_calibration_evidence_coverage",
    "calibration_evidence_coverage_payload",
]
