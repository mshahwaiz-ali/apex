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
    """Return calibration metrics from canonical filled trades only.

    Pre-entry invalidation, expiry, and missed-entry records remain part of the
    operational backtest history, but they are not executed trades and cannot
    contribute to win rate, expectancy, excursion, or calibration authority.
    """

    filled = _filled_trades(report)
    total = len(filled)
    if not total:
        return {}

    wins = tuple(trade for trade in filled if trade.net_pnl > 0.0)
    losses = tuple(trade for trade in filled if trade.net_pnl < 0.0)
    gross_profit = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    realized_r = sum(trade.realized_r_multiple for trade in filled)

    metrics = {
        CalibrationMetric.WIN_RATE.value: len(wins) / total,
        CalibrationMetric.EXPECTANCY.value: sum(trade.net_pnl for trade in filled) / total,
        CalibrationMetric.AVERAGE_R.value: realized_r / total,
        CalibrationMetric.TP1_HIT_RATE.value: (
            sum(_partial_target_count(trade) >= 1 for trade in filled) / total
        ),
        CalibrationMetric.TP2_HIT_RATE.value: (
            sum(_partial_target_count(trade) >= 2 for trade in filled) / total
        ),
        CalibrationMetric.STOP_RATE.value: (
            sum(trade.outcome is BacktestOutcome.STOP for trade in filled) / total
        ),
        CalibrationMetric.MFE.value: (
            sum(float(trade.metadata.get("maximum_favorable_excursion_r", 0.0)) for trade in filled)
            / total
        ),
        CalibrationMetric.MAE.value: (
            sum(float(trade.metadata.get("maximum_adverse_excursion_r", 0.0)) for trade in filled)
            / total
        ),
    }
    if gross_loss > 0.0:
        metrics[CalibrationMetric.PROFIT_FACTOR.value] = gross_profit / gross_loss

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
        sample_size=len(_filled_trades(report)),
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


def _filled_trades(report: BacktestReport) -> tuple[SimulatedTrade, ...]:
    """Return only records that represent an actual historical entry fill."""

    return tuple(trade for trade in report.trades if trade.metadata.get("entry_filled") is True)


def _partial_target_count(trade: SimulatedTrade) -> int:
    value = trade.metadata.get("partial_target_count", 0)
    return int(value) if isinstance(value, int | float) else 0


__all__ = [
    "calibration_acceptance_from_report",
    "calibration_metrics_from_report",
    "calibration_reporting_payload",
]
