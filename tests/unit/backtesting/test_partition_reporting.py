from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    HistoricalSignalSplit,
    SimulatedTrade,
    build_partition_stability_report,
    partition_stability_payload,
    summarize_trades,
)
from apex.strategies import StrategyType, TradeDirection


def _report(*net_pnls: float):
    trades = tuple(_trade(index=index, net_pnl=value) for index, value in enumerate(net_pnls))
    return summarize_trades(trades)


def _trade(*, index: int, net_pnl: float) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol=f"TEST{index}USDT",
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
    outcome = BacktestOutcome.TARGET if net_pnl > 0.0 else BacktestOutcome.STOP
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=datetime(2026, 1, 2, tzinfo=UTC),
        exit_price=110.0 if net_pnl > 0.0 else 95.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / 5.0,
        holding_candles=2,
    )


def test_partition_reporting_preserves_chronological_split_order() -> None:
    report = build_partition_stability_report(
        {
            HistoricalSignalSplit.FINAL_TEST: _report(2.0, 4.0),
            HistoricalSignalSplit.TRAIN: _report(4.0, 6.0),
            HistoricalSignalSplit.VALIDATION: _report(3.0, 5.0),
        }
    )

    assert tuple(item.split for item in report.partitions) == (
        HistoricalSignalSplit.TRAIN,
        HistoricalSignalSplit.VALIDATION,
        HistoricalSignalSplit.FINAL_TEST,
    )
    assert report.complete is True
    assert report.all_partitions_sampled is True
    assert report.all_expectancies_positive is True
    assert report.expectancy_spread == pytest.approx(2.0)
    assert report.calibration_authoritative is False


def test_partition_reporting_fails_closed_when_a_split_is_missing() -> None:
    report = build_partition_stability_report(
        {
            HistoricalSignalSplit.TRAIN: _report(4.0),
            HistoricalSignalSplit.VALIDATION: _report(3.0),
        }
    )
    payload = partition_stability_payload(report)

    assert report.complete is False
    assert report.all_partitions_sampled is False
    assert report.all_expectancies_positive is None
    assert report.expectancy_spread is None
    assert report.missing_splits == (HistoricalSignalSplit.FINAL_TEST,)
    assert payload["missing_splits"] == ["final_test"]
    assert payload["calibration_authoritative"] is False


def test_negative_final_test_expectancy_is_reported_without_threshold_tuning() -> None:
    report = build_partition_stability_report(
        {
            HistoricalSignalSplit.TRAIN: _report(4.0),
            HistoricalSignalSplit.VALIDATION: _report(3.0),
            HistoricalSignalSplit.FINAL_TEST: _report(-2.0),
        }
    )

    assert report.complete is True
    assert report.all_partitions_sampled is True
    assert report.all_expectancies_positive is False
    assert report.partitions[-1].positive_expectancy is False
    assert report.calibration_authoritative is False


def test_empty_partition_blocks_stability_conclusions() -> None:
    report = build_partition_stability_report(
        {
            HistoricalSignalSplit.TRAIN: _report(4.0),
            HistoricalSignalSplit.VALIDATION: _report(),
            HistoricalSignalSplit.FINAL_TEST: _report(2.0),
        }
    )

    assert report.complete is True
    assert report.all_partitions_sampled is False
    assert report.all_expectancies_positive is None
    assert report.expectancy_spread is None
