"""Typed calibration and acceptance metrics for backtest reporting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real


class CalibrationMetric(StrEnum):
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTANCY = "expectancy"
    AVERAGE_R = "average_r"
    TP1_HIT_RATE = "tp1_hit_rate"
    TP2_HIT_RATE = "tp2_hit_rate"
    RUNNER_SUCCESS_RATE = "runner_success_rate"
    STOP_RATE = "stop_rate"
    FALSE_CMP_SIGNAL_RATE = "false_cmp_signal_rate"
    MFE = "maximum_favorable_excursion_r"
    MAE = "maximum_adverse_excursion_r"
    FEES_AND_SLIPPAGE = "fees_and_slippage"
    LIQUIDATION_OR_MARGIN_FAILURE_RATE = "liquidation_or_margin_failure_rate"


_REQUIRED_METRICS = tuple(CalibrationMetric)


@dataclass(frozen=True, slots=True)
class CalibrationAcceptanceReport:
    sample_size: int
    available_metrics: tuple[CalibrationMetric, ...]
    missing_metrics: tuple[CalibrationMetric, ...]
    positive_expectancy: bool | None
    acceptable_drawdown: bool | None
    stable_regime_performance: bool | None
    confidence_claims_allowed: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise ValueError("sample size must be non-negative")
        if len(set(self.available_metrics)) != len(self.available_metrics):
            raise ValueError("available metrics must be unique")
        if len(set(self.missing_metrics)) != len(self.missing_metrics):
            raise ValueError("missing metrics must be unique")
        if set(self.available_metrics) & set(self.missing_metrics):
            raise ValueError("available and missing metrics must not overlap")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("acceptance blockers must be unique")
        expected_allowed = (
            self.sample_size > 0
            and not self.missing_metrics
            and self.positive_expectancy is True
            and self.acceptable_drawdown is True
            and self.stable_regime_performance is True
            and not self.blockers
        )
        if self.confidence_claims_allowed is not expected_allowed:
            raise ValueError("confidence claim authority must match acceptance evidence")


def evaluate_calibration_acceptance(
    metrics: Mapping[str, object],
    *,
    sample_size: int,
    acceptable_drawdown: bool | None,
    stable_regime_performance: bool | None,
) -> CalibrationAcceptanceReport:
    """Fail closed until required metrics and acceptance evidence are present."""

    available = tuple(
        metric for metric in _REQUIRED_METRICS if _is_numeric(metrics.get(metric.value))
    )
    missing = tuple(metric for metric in _REQUIRED_METRICS if metric not in available)

    expectancy_value = metrics.get(CalibrationMetric.EXPECTANCY.value)
    positive_expectancy = float(expectancy_value) > 0.0 if _is_numeric(expectancy_value) else None

    blockers: list[str] = []
    if sample_size <= 0:
        blockers.append("sample_size_unavailable")
    if missing:
        blockers.append("required_metrics_incomplete")
    if positive_expectancy is not True:
        blockers.append(
            "expectancy_unavailable" if positive_expectancy is None else "expectancy_not_positive"
        )
    if acceptable_drawdown is not True:
        blockers.append(
            "drawdown_unavailable" if acceptable_drawdown is None else "drawdown_not_acceptable"
        )
    if stable_regime_performance is not True:
        blockers.append(
            "regime_stability_unavailable"
            if stable_regime_performance is None
            else "regime_performance_unstable"
        )

    blockers_tuple = tuple(sorted(set(blockers)))
    confidence_claims_allowed = (
        sample_size > 0
        and not missing
        and positive_expectancy is True
        and acceptable_drawdown is True
        and stable_regime_performance is True
        and not blockers_tuple
    )
    return CalibrationAcceptanceReport(
        sample_size=sample_size,
        available_metrics=available,
        missing_metrics=missing,
        positive_expectancy=positive_expectancy,
        acceptable_drawdown=acceptable_drawdown,
        stable_regime_performance=stable_regime_performance,
        confidence_claims_allowed=confidence_claims_allowed,
        blockers=blockers_tuple,
    )


def calibration_acceptance_payload(
    report: CalibrationAcceptanceReport,
) -> dict[str, object]:
    return {
        "sample_size": report.sample_size,
        "available_metrics": [metric.value for metric in report.available_metrics],
        "missing_metrics": [metric.value for metric in report.missing_metrics],
        "positive_expectancy": report.positive_expectancy,
        "acceptable_drawdown": report.acceptable_drawdown,
        "stable_regime_performance": report.stable_regime_performance,
        "confidence_claims_allowed": report.confidence_claims_allowed,
        "blockers": list(report.blockers),
        "acceptance_principle": (
            "calibrated precision + positive expectancy + tolerable drawdown + "
            "stable regime performance"
        ),
    }


def _is_numeric(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


__all__ = [
    "CalibrationAcceptanceReport",
    "CalibrationMetric",
    "calibration_acceptance_payload",
    "evaluate_calibration_acceptance",
]
