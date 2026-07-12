from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.structure import (
    BreakQuality,
    ConfirmationStatus,
    PivotStatus,
    SwingPoint,
    SwingType,
    detect_structure_breaks,
)


def _candle(index: int, *, high: float, low: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=(high + low) / 2,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def test_later_close_break_is_not_hidden_by_earlier_wick_probe() -> None:
    candles = (
        _candle(0, high=99.0, low=95.0, close=98.0),
        _candle(1, high=100.0, low=96.0, close=99.0),
        _candle(2, high=101.0, low=97.0, close=99.5),
        _candle(3, high=103.0, low=99.0, close=102.0),
    )
    swing = SwingPoint(
        index=1,
        time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=1),
        price=100.0,
        kind=SwingType.HIGH,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )

    event = detect_structure_breaks(candles, (swing,))[0]

    assert event.candle_index == 3
    assert event.quality in {BreakQuality.VALID, BreakQuality.STRONG}
    assert event.confirmation is ConfirmationStatus.CONFIRMED
