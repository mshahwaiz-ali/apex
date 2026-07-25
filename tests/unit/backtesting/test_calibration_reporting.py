from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    SimulatedTrade,
    calibration_acceptance_from_report,
    calibration_metrics_from_report,
    calibration_reporting_payload,
    summarize_trades,
)
from apex.backtesting.acceptance import CalibrationMetric
from apex.strategies import StrategyType, TradeDirection


def _trade(
    *,
    outcome: BacktestOutcome,
    net_pnl: float,
    realized_r: float,
    partial_target_count: int,
    mfe_r: float,
    mae_r: float,
    entry_filled: bool = True,
) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=70.0,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=datetime(2026, 1, 2, tzinfo=UTC),
        exit_price=110.0 if outcome is BacktestOutcome.TARGET else 95.0,
        gross_pnl=net_pnl + 0.1,
        fees=0.1,
        net_pnl=net_pnl,
        realized_r_multiple=realized_r,
        holding_candles=2,
        metadata={
            "entry_filled": entry_filled,
            "partial_target_count": partial_target_count,
            "maximum_favorable_excursion_r": mfe_r,
            "maximum_adverse_excursion_r": mae_r,
        },
    )


def _report():
    return summarize_trades(
        (
            _trade(
                outcome=BacktestOutcome.TARGET,
                net_pnl=10.0,
                realized_r=2.0,
                partial_target_count=2,
                mfe_r=2.4,
                mae_r=0.3,
            ),
            _trade(
                outcome=BacktestOutcome.STOP,
                net_pnl=-5.0,
                realized_r=-1.0,
                partial_target_count=0,
                mfe_r=0.2,
                mae_r=1.1,
            ),
        )
    )


def test_reporting_derives_only_metrics_supported_by_existing_backtest() -> None:
    metrics = calibration_metrics_from_report(_report())

    assert metrics[CalibrationMetric.WIN_RATE.value] == 0.5
    assert metrics[CalibrationMetric.PROFIT_FACTOR.value] == 2.0
    assert metrics[CalibrationMetric.EXPECTANCY.value] == 2.5
    assert metrics[CalibrationMetric.AVERAGE_R.value] == 0.5
    assert metrics[CalibrationMetric.TP1_HIT_RATE.value] == 0.5
    assert metrics[CalibrationMetric.TP2_HIT_RATE.value] == 0.5
    assert metrics[CalibrationMetric.STOP_RATE.value] == 0.5
    assert metrics[CalibrationMetric.MFE.value] == 1.3
    assert metrics[CalibrationMetric.MAE.value] == pytest.approx(0.7)
    assert CalibrationMetric.RUNNER_SUCCESS_RATE.value not in metrics
    assert CalibrationMetric.FALSE_CMP_SIGNAL_RATE.value not in metrics
    assert CalibrationMetric.FEES_AND_SLIPPAGE.value not in metrics
    assert CalibrationMetric.LIQUIDATION_OR_MARGIN_FAILURE_RATE.value not in metrics


def test_reporting_remains_non_authoritative_when_evidence_is_incomplete() -> None:
    report = _report()
    acceptance = calibration_acceptance_from_report(report)
    payload = calibration_reporting_payload(report)

    assert acceptance.sample_size == 2
    assert acceptance.confidence_claims_allowed is False
    assert acceptance.blockers == (
        "drawdown_unavailable",
        "regime_stability_unavailable",
        "required_metrics_incomplete",
    )
    assert payload["calibration_authoritative"] is False
    acceptance_payload = payload["acceptance"]
    assert isinstance(acceptance_payload, dict)
    assert acceptance_payload["confidence_claims_allowed"] is False


def test_external_gates_cannot_override_missing_backtest_metrics() -> None:
    acceptance = calibration_acceptance_from_report(
        _report(),
        acceptable_drawdown=True,
        stable_regime_performance=True,
    )

    assert acceptance.positive_expectancy is True
    assert acceptance.confidence_claims_allowed is False
    assert acceptance.blockers == ("required_metrics_incomplete",)


def test_calibration_excludes_unfilled_lifecycle_records() -> None:
    report = summarize_trades(
        (
            _trade(
                outcome=BacktestOutcome.TARGET,
                net_pnl=10.0,
                realized_r=2.0,
                partial_target_count=2,
                mfe_r=2.4,
                mae_r=0.3,
            ),
            _trade(
                outcome=BacktestOutcome.PRE_ENTRY_INVALIDATED,
                net_pnl=0.0,
                realized_r=0.0,
                partial_target_count=0,
                mfe_r=8.0,
                mae_r=6.0,
                entry_filled=False,
            ),
            _trade(
                outcome=BacktestOutcome.ACTIVATION_EXPIRED,
                net_pnl=0.0,
                realized_r=0.0,
                partial_target_count=0,
                mfe_r=7.0,
                mae_r=5.0,
                entry_filled=False,
            ),
        )
    )

    metrics = calibration_metrics_from_report(report)
    acceptance = calibration_acceptance_from_report(report)

    assert metrics[CalibrationMetric.WIN_RATE.value] == 1.0
    assert metrics[CalibrationMetric.EXPECTANCY.value] == 10.0
    assert metrics[CalibrationMetric.AVERAGE_R.value] == 2.0
    assert metrics[CalibrationMetric.TP1_HIT_RATE.value] == 1.0
    assert metrics[CalibrationMetric.TP2_HIT_RATE.value] == 1.0
    assert metrics[CalibrationMetric.STOP_RATE.value] == 0.0
    assert metrics[CalibrationMetric.MFE.value] == 2.4
    assert metrics[CalibrationMetric.MAE.value] == 0.3
    assert acceptance.sample_size == 1


def test_calibration_has_no_performance_metrics_without_filled_trades() -> None:
    report = summarize_trades(
        (
            _trade(
                outcome=BacktestOutcome.MISSED_ENTRY,
                net_pnl=0.0,
                realized_r=0.0,
                partial_target_count=0,
                mfe_r=3.0,
                mae_r=2.0,
                entry_filled=False,
            ),
        )
    )

    assert calibration_metrics_from_report(report) == {}
    assert calibration_acceptance_from_report(report).sample_size == 0
