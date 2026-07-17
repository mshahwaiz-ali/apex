from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.structure import RangeBreakoutState, detect_range


def _candle(index: int, high: float, low: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    midpoint = (high + low) / 2
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=midpoint,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def _base_range() -> list[Candle]:
    candles: list[Candle] = []
    for index in range(20):
        high = 102.0 if index % 4 == 0 else 101.5
        low = 98.0 if index % 4 == 2 else 98.5
        candles.append(_candle(index, high, low, 100.0))
    return candles


def test_detect_range_returns_stable_recent_range() -> None:
    candles = tuple([*_base_range(), _candle(20, 101.0, 99.0, 100.5)])

    result = detect_range(candles)

    assert result is not None
    assert result.low == 98.0
    assert result.high == 102.0
    assert result.breakout_state is RangeBreakoutState.NONE


def test_detect_range_classifies_close_confirmed_breakout() -> None:
    candles = tuple([*_base_range(), _candle(20, 104.0, 101.0, 103.0)])

    result = detect_range(candles)

    assert result is not None
    assert result.breakout_state is RangeBreakoutState.BULLISH


def test_detect_range_classifies_false_breakout() -> None:
    candles = tuple([*_base_range(), _candle(20, 104.0, 99.0, 101.0)])

    result = detect_range(candles)

    assert result is not None
    assert result.breakout_state is RangeBreakoutState.FALSE_BULLISH
    assert result.false_break_indices == (20,)
