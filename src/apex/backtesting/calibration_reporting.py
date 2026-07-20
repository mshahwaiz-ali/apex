"""Calibration reporting adapters for existing chronological backtests."""

from __future__ import annotations

from apex.backtesting.acceptance import (
    CalibrationAcceptanceReport,
    CalibrationMetric,
    calibration_acceptance_payload,
    evaluate_calibration_acceptance,
)
from apex.backtesting.contracts import BacktestOutcome, BacktestReport, SimulatedTrade


def calibration_metrics_from_report(report: BacktestReport) -> dict[str, float]:
    """Return only metrics defensibly available from the existing report.

    Unsupported metrics remain absent so the acceptance contract fails closed
    instead of fabricating historical evidence.
    """

    metrics = {
        CalibrationMetric.WIN_RATE.value: report.win_rate,
        CalibrationMetric.EXPECTANCY.value: report.expectancy,
        CalibrationMetric.AVERAGE_R.value: report.average_risk_reward,
    }
    if report.profit_factor is not None:
        metrics[CalibrationMetric.PROFIT_FACTOR.value] = report.profit_factor

    total = report.total_trades
    if total:
        metrics[CalibrationMetric.TP1_HIT_RATE.value] = (
            sum(_partial_target_count(trade) >= 1 for trade in report.trades) / total
        )
        metrics[CalibrationMetric.TP2_HIT_RATE.value] = (
            sum(_partial_target_count(trade) >= 2 for trade in report.trades) / total
        )
        metrics[CalibrationMetric.STOP_RATE.value] = (
            sum(trade.outcome is BacktestOutcome.STOP for trade in report.trades) / total
        )
        metrics[CalibrationMetric.MFE.value] = (
            sum(
                float(trade.metadata.get("maximum_favorable_excursion_r", 0.0))
                for trade in report.trades
            )
            / total
        )
        metrics[CalibrationMetric.MAE.value] = (
            sum(
                float(trade.metadata.get("maximum_adverse_excursion_r", 0.0))
                for trade in report.trades
            )
            / total
        )

    return metrics


def calibration_acceptance_from_report(
    report: BacktestReport,
    *,
    acceptable_drawdown: bool | None = None,
    stable_regime_performance: bool | None = None,
) -> CalibrationAcceptanceReport:
    """Evaluate an existing report without making unsupported acceptance claims."""

    return evaluate_calibration_acceptance(
        calibration_metrics_from_report(report),
        sample_size=report.total_trades,
        acceptable_drawdown=acceptable_drawdown,
        stable_regime_performance=stable_regime_performance,
    )


def calibration_reporting_payload(
    report: BacktestReport,
    *,
    acceptable_drawdown: bool | None = None,
    stable_regime_performance: bool | None = None,
) -> dict[str, object]:
    """Return derived metrics together with the fail-closed acceptance result."""

    metrics = calibration_metrics_from_report(report)
    acceptance = calibration_acceptance_from_report(
        report,
        acceptable_drawdown=acceptable_drawdown,
        stable_regime_performance=stable_regime_performance,
    )
    return {
        "metrics": metrics,
        "acceptance": calibration_acceptance_payload(acceptance),
        "calibration_authoritative": acceptance.confidence_claims_allowed,
    }


def _partial_target_count(trade: SimulatedTrade) -> int:
    value = trade.metadata.get("partial_target_count", 0)
    return int(value) if isinstance(value, int | float) else 0


__all__ = [
    "calibration_acceptance_from_report",
    "calibration_metrics_from_report",
    "calibration_reporting_payload",
]
