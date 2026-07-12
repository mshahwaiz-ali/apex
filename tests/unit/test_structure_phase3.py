from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import Candle
from apex.structure import (
    ComparisonPolicy,
    PivotStatus,
    SwingPoint,
    SwingType,
    TrendDirection,
    classify_trend,
    create_default_structure_registry,
    detect_swings,
)


def _candles(highs: list[float], lows: list[float], *, active_final: bool = False) -> tuple[Candle, ...]:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    items: list[Candle] = []
    for index, (high, low) in enumerate(zip(highs, lows, strict=True)):
        midpoint = (high + low) / 2
        items.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=opened + timedelta(minutes=index),
                close_time=opened + timedelta(minutes=index + 1),
                open=midpoint,
                high=high,
                low=low,
                close=midpoint,
                volume=10.0,
                is_closed=not (active_final and index == len(highs) - 1),
                source="fixture",
            )
        )
    return tuple(items)


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


def test_detect_swings_finds_clear_high_and_low() -> None:
    candles = _candles([101, 103, 102, 104, 102], [99, 100, 98, 100, 97])

    swings = detect_swings(candles, left_window=1, right_window=1)

    assert [(item.index, item.kind) for item in swings] == [
        (1, SwingType.HIGH),
        (2, SwingType.LOW),
        (3, SwingType.HIGH),
    ]


def test_non_strict_equal_high_uses_earliest_tie() -> None:
    candles = _candles([101, 103, 103, 102], [99, 100, 100, 99])

    swings = detect_swings(
        candles,
        left_window=1,
        right_window=1,
        comparison_policy=ComparisonPolicy.NON_STRICT,
    )

    assert [(item.index, item.kind) for item in swings if item.kind is SwingType.HIGH] == [
        (1, SwingType.HIGH)
    ]


def test_developing_pivot_is_not_silently_confirmed() -> None:
    candles = _candles([101, 102, 104], [99, 100, 101])

    confirmed_only = detect_swings(candles, left_window=1, right_window=2)
    including_edge = detect_swings(
        candles,
        left_window=1,
        right_window=2,
        include_developing=True,
    )

    assert confirmed_only == ()
    assert including_edge[-1].status is PivotStatus.DEVELOPING


def test_default_policy_drops_active_final_candle() -> None:
    candles = _candles([101, 103, 102, 110], [99, 100, 98, 101], active_final=True)

    swings = detect_swings(candles, left_window=1, right_window=1)

    assert all(item.index < len(candles) - 1 for item in swings)


def test_clean_higher_high_higher_low_sequence_is_strong_bullish() -> None:
    swings = (
        _swing(1, 105, SwingType.HIGH),
        _swing(2, 100, SwingType.LOW),
        _swing(3, 110, SwingType.HIGH),
        _swing(4, 103, SwingType.LOW),
        _swing(5, 115, SwingType.HIGH),
        _swing(6, 106, SwingType.LOW),
    )

    result = classify_trend(swings)

    assert result.direction is TrendDirection.STRONG_BULLISH
    assert result.evidence.higher_highs == 2
    assert result.evidence.higher_lows == 2


def test_structure_registry_names_are_stable() -> None:
    registry = create_default_structure_registry()

    assert registry.names == ("market_structure",)
    with pytest.raises(KeyError):
        registry.get("private_helper")
