from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.structure import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    PivotStatus,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
    detect_changes_of_character,
    detect_structure_breaks,
)


def _candle(index: int, high: float, low: float, close: float, *, closed: bool = True) -> Candle:
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
        is_closed=closed,
        source="fixture",
    )


def _swing(index: int, price: float, kind: SwingType) -> SwingPoint:
    return SwingPoint(
        index=index,
        time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        price=price,
        kind=kind,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )


def test_close_confirmed_bullish_break() -> None:
    candles = (
        _candle(0, 99, 95, 98),
        _candle(1, 100, 96, 99),
        _candle(2, 103, 98, 102),
    )

    events = detect_structure_breaks(candles, (_swing(1, 100, SwingType.HIGH),))

    assert len(events) == 1
    assert events[0].direction is BreakDirection.BULLISH
    assert events[0].quality in {BreakQuality.VALID, BreakQuality.STRONG}
    assert events[0].confirmation is ConfirmationStatus.CONFIRMED


def test_wick_only_breach_is_rejected() -> None:
    candles = (
        _candle(0, 99, 95, 98),
        _candle(1, 100, 96, 99),
        _candle(2, 102, 97, 99),
    )

    events = detect_structure_breaks(candles, (_swing(1, 100, SwingType.HIGH),))

    assert events[0].quality is BreakQuality.WICK_ONLY
    assert events[0].confirmation is ConfirmationStatus.REJECTED


def test_duplicate_break_events_are_removed() -> None:
    swing = _swing(1, 100, SwingType.HIGH)
    candles = (
        _candle(0, 99, 95, 98),
        _candle(1, 100, 96, 99),
        _candle(2, 103, 98, 102),
    )

    events = detect_structure_breaks(candles, (swing, swing))

    assert len(events) == 1


def test_opposing_valid_break_creates_choch() -> None:
    candles = (
        _candle(0, 105, 101, 104),
        _candle(1, 104, 100, 103),
        _candle(2, 102, 97, 98),
    )
    break_event = detect_structure_breaks(
        candles,
        (_swing(1, 100, SwingType.LOW),),
    )[0]
    trend = TrendAnalysis(
        direction=TrendDirection.BULLISH,
        strength=0.8,
        evidence=TrendEvidence(persistence=0.8),
    )

    changes = detect_changes_of_character(trend, (break_event,))

    assert len(changes) == 1
    assert changes[0].prior_trend is TrendDirection.BULLISH
    assert changes[0].break_event.direction is BreakDirection.BEARISH


def test_break_without_prior_directional_trend_is_not_choch() -> None:
    candles = (
        _candle(0, 105, 101, 104),
        _candle(1, 104, 100, 103),
        _candle(2, 102, 97, 98),
    )
    break_event = detect_structure_breaks(
        candles,
        (_swing(1, 100, SwingType.LOW),),
    )[0]
    trend = TrendAnalysis(
        direction=TrendDirection.RANGE,
        strength=0.0,
        evidence=TrendEvidence(),
    )

    assert detect_changes_of_character(trend, (break_event,)) == ()
