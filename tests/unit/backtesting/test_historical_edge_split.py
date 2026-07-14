"""Tests for chronological historical edge dataset splits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.historical_edge_split import (
    HistoricalEdgeSplitConfig,
    HistoricalEdgeSplitRole,
    split_historical_edge_trades,
)
from apex.strategies import StrategyType, TradeDirection


def _trade(index: int, *, hold_minutes: int = 2) -> SimulatedTrade:
    generated_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5)
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=75.0,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET,
        exit_time=generated_at + timedelta(minutes=hold_minutes),
        exit_price=102.0,
        gross_pnl=1.05,
        fees=0.05,
        net_pnl=1.0,
        realized_r_multiple=1.0,
        holding_candles=1,
    )


def test_default_split_is_chronological_and_deterministic() -> None:
    trades = tuple(reversed(tuple(_trade(index) for index in range(10))))

    split_set = split_historical_edge_trades(trades)

    assert split_set.source_trade_count == 10
    assert tuple(trade.signal.generated_at.minute for trade in split_set.train.trades) == (
        0,
        5,
        10,
        15,
        20,
        25,
    )
    assert len(split_set.validation.trades) == 2
    assert len(split_set.test.trades) == 2
    assert split_set.train.role is HistoricalEdgeSplitRole.TRAIN
    assert split_set.validation.role is HistoricalEdgeSplitRole.VALIDATION
    assert split_set.test.role is HistoricalEdgeSplitRole.TEST
    assert split_set.validation.start_time is not None
    assert split_set.train.end_time is not None
    assert split_set.validation.start_time > split_set.train.end_time


def test_boundary_purge_removes_configured_trades() -> None:
    split_set = split_historical_edge_trades(
        tuple(_trade(index) for index in range(10)),
        config=HistoricalEdgeSplitConfig(purge_trades=1),
    )

    assert len(split_set.train.trades) == 6
    assert len(split_set.validation.trades) == 1
    assert len(split_set.test.trades) == 1
    assert split_set.validation.purged_trade_count == 1
    assert split_set.test.purged_trade_count == 1


def test_overlap_guard_removes_later_entries_before_prior_exit() -> None:
    trades = tuple(
        _trade(index, hold_minutes=12 if index in {5, 7} else 2)
        for index in range(10)
    )

    split_set = split_historical_edge_trades(trades)

    assert split_set.validation.overlap_removed_count == 2
    assert split_set.validation.trades == ()
    assert split_set.test.overlap_removed_count == 1
    assert len(split_set.test.trades) == 1
    assert split_set.train.end_time is not None
    assert split_set.test.start_time is not None
    assert split_set.test.start_time > split_set.train.end_time


def test_empty_source_produces_three_empty_splits() -> None:
    split_set = split_historical_edge_trades(())

    assert split_set.source_trade_count == 0
    assert split_set.train.trades == ()
    assert split_set.validation.trades == ()
    assert split_set.test.trades == ()
    assert split_set.train.start_time is None
    assert split_set.test.end_time is None


@pytest.mark.parametrize(
    "config",
    (
        HistoricalEdgeSplitConfig(train_ratio=0.5, validation_ratio=0.25, test_ratio=0.25),
        HistoricalEdgeSplitConfig(train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15),
    ),
)
def test_custom_valid_ratios_are_supported(config: HistoricalEdgeSplitConfig) -> None:
    split_set = split_historical_edge_trades(
        tuple(_trade(index) for index in range(20)),
        config=config,
    )

    assert len(split_set.train.trades) == int(20 * config.train_ratio)
    assert split_set.source_trade_count == 20


def test_invalid_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="must sum to one"):
        HistoricalEdgeSplitConfig(
            train_ratio=0.5,
            validation_ratio=0.3,
            test_ratio=0.3,
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        HistoricalEdgeSplitConfig(purge_trades=-1)
    with pytest.raises(ValueError, match="positive and finite"):
        HistoricalEdgeSplitConfig(train_ratio=0.0, validation_ratio=0.5, test_ratio=0.5)
