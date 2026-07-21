from datetime import UTC, datetime, timedelta

from apex.domain.models import Candle
from apex.strategies.contracts import TradeDirection
from apex.strategies.reversal_watch import (
    ReversalWatchState,
    classify_reversal_watch,
)

NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        symbol="TESTUSDT",
        timeframe="5m",
        open_time=NOW + timedelta(minutes=index * 5),
        close_time=NOW + timedelta(minutes=(index + 1) * 5),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        is_closed=True,
        source="test",
    )


def test_bullish_reclaim_watch_is_not_automatic_long() -> None:
    candles = (
        _candle(0, open_price=100.0, high=100.2, low=97.5, close=98.0),
        _candle(1, open_price=98.0, high=98.2, low=96.0, close=96.5),
        _candle(2, open_price=96.5, high=97.4, low=96.2, close=97.2),
    )

    result = classify_reversal_watch(
        candles=candles,
        exhausted_direction=TradeDirection.SHORT,
        reclaim_level=97.5,
        atr=2.0,
    )

    assert result.state is ReversalWatchState.WATCH
    assert result.reversal_direction is TradeDirection.LONG
    assert result.reclaim_complete is False
    assert result.may_create_reversal_candidate is False
    assert result.trigger_required is True


def test_failed_breakdown_can_trigger_only_after_reclaim() -> None:
    candles = (
        _candle(0, open_price=100.0, high=100.2, low=97.5, close=98.0),
        _candle(1, open_price=98.0, high=98.1, low=96.0, close=96.4),
        _candle(2, open_price=96.4, high=98.0, low=96.2, close=97.8),
    )

    result = classify_reversal_watch(
        candles=candles,
        exhausted_direction=TradeDirection.SHORT,
        reclaim_level=97.5,
        atr=2.0,
    )

    assert result.state is ReversalWatchState.TRIGGERED
    assert result.swing_failure is True
    assert result.recovery_present is True
    assert result.reclaim_complete is True
    assert result.may_create_reversal_candidate is True
    assert result.trigger_required is False


def test_exhausted_long_without_bearish_recovery_has_no_automatic_short() -> None:
    candles = (
        _candle(0, open_price=100.0, high=102.0, low=99.8, close=101.8),
        _candle(1, open_price=101.8, high=103.0, low=101.5, close=102.7),
        _candle(2, open_price=102.7, high=103.2, low=102.4, close=103.0),
    )

    result = classify_reversal_watch(
        candles=candles,
        exhausted_direction=TradeDirection.LONG,
        reclaim_level=102.0,
        atr=2.0,
    )

    assert result.state is ReversalWatchState.NONE
    assert result.reversal_direction is TradeDirection.SHORT
    assert result.may_create_reversal_candidate is False


def test_bearish_reclaim_trigger_is_directionally_symmetric() -> None:
    candles = (
        _candle(0, open_price=100.0, high=102.0, low=99.7, close=101.7),
        _candle(1, open_price=101.7, high=103.0, low=101.5, close=102.6),
        _candle(2, open_price=102.6, high=102.8, low=100.8, close=101.0),
    )

    result = classify_reversal_watch(
        candles=candles,
        exhausted_direction=TradeDirection.LONG,
        reclaim_level=101.5,
        atr=2.0,
    )

    assert result.state is ReversalWatchState.TRIGGERED
    assert result.reversal_direction is TradeDirection.SHORT
    assert result.reclaim_complete is True
    assert result.may_create_reversal_candidate is True
