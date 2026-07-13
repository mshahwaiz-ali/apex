from datetime import UTC, datetime, timedelta

import pytest

from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    _is_in_cooldown,
    _is_overlapping,
)
from apex.backtesting import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 1, 1, tzinfo=UTC)
FINGERPRINT = ("BTC/USDT", "trend_pullback", "long")


def _trade(exit_time: datetime) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=80.0,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.EXPIRED,
        exit_time=exit_time,
        exit_price=100.0,
        gross_pnl=0.0,
        fees=0.0,
        net_pnl=0.0,
        realized_r_multiple=0.0,
        holding_candles=1,
    )


def test_overlap_is_true_only_before_previous_exit() -> None:
    trade = _trade(NOW + timedelta(minutes=15))

    assert _is_overlapping((trade,), NOW + timedelta(minutes=10))
    assert not _is_overlapping((trade,), NOW + timedelta(minutes=15))


def test_matching_setup_is_suppressed_inside_cooldown() -> None:
    assert _is_in_cooldown(FINGERPRINT, FINGERPRINT, 12, 10, 3)
    assert not _is_in_cooldown(FINGERPRINT, FINGERPRINT, 14, 10, 3)
    assert not _is_in_cooldown(FINGERPRINT, None, 12, None, 3)


def test_request_rejects_invalid_spacing_controls() -> None:
    with pytest.raises(ValueError, match="decision interval"):
        ChronologicalBacktestRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": ()},
            analysis_timeframes=("5m",),
            replay_timeframe="5m",
            decision_interval_candles=0,
        )

    with pytest.raises(ValueError, match="cooldown"):
        ChronologicalBacktestRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": ()},
            analysis_timeframes=("5m",),
            replay_timeframe="5m",
            candidate_cooldown_candles=-1,
        )
