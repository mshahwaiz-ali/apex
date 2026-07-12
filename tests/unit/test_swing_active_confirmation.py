from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.features import ActiveCandlePolicy
from apex.structure import PivotStatus, SwingType, detect_swings


def _candles(*, active_final: bool) -> tuple[Candle, ...]:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    highs = (101.0, 105.0, 102.0)
    lows = (99.0, 100.0, 98.0)
    return tuple(
        Candle(
            symbol="BTC/USDT",
            timeframe="1m",
            open_time=opened + timedelta(minutes=index),
            close_time=opened + timedelta(minutes=index + 1),
            open=(high + low) / 2,
            high=high,
            low=low,
            close=(high + low) / 2,
            volume=10.0,
            is_closed=not (active_final and index == 2),
            source="fixture",
        )
        for index, (high, low) in enumerate(zip(highs, lows, strict=True))
    )


def test_active_right_candle_cannot_confirm_swing() -> None:
    developing = detect_swings(
        _candles(active_final=True),
        left_window=1,
        right_window=1,
        include_developing=True,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    confirmed = detect_swings(
        _candles(active_final=False),
        left_window=1,
        right_window=1,
    )

    active_high = next(
        swing
        for swing in developing
        if swing.index == 1 and swing.kind is SwingType.HIGH
    )
    closed_high = next(
        swing
        for swing in confirmed
        if swing.index == 1 and swing.kind is SwingType.HIGH
    )
    assert active_high.status is PivotStatus.DEVELOPING
    assert closed_high.status is PivotStatus.CONFIRMED
