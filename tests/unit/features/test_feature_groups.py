from datetime import UTC, datetime, timedelta

import pytest
from apex.features.price_location import (
    bollinger_position,
    distance_from_recent_extremes,
    recent_range_position,
    vwap,
)

from apex.domain.models import Candle
from apex.features.trend import (
    ema_relationship,
    ema_slope,
    price_distance_from_ema,
    trend_persistence,
)
from apex.features.volume import average_volume, relative_volume, volume_pressure, volume_spike

START = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)


def make_candles(count: int = 40) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        close = 100.0 + index
        open_time = START + timedelta(minutes=15 * index)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=15),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=100.0 + index,
                is_closed=True,
                source="test",
            )
        )
    return candles


def test_volume_features_are_aligned_and_bounded() -> None:
    candles = make_candles()
    average = average_volume(candles, 5)
    relative = relative_volume(candles, 5)
    spike = volume_spike(candles, 5, threshold=1.0)
    pressure = volume_pressure(candles, 5)

    assert len(average.values) == len(candles)
    assert relative.latest is not None and relative.latest > 0
    assert spike.latest == 1.0
    assert pressure.bullish.latest == pytest.approx(1.0)
    assert pressure.bearish.latest == pytest.approx(0.0)


def test_location_features_are_deterministic() -> None:
    candles = make_candles()
    position = recent_range_position(candles, 5)
    high_distance, low_distance = distance_from_recent_extremes(candles, 5)
    weighted = vwap(candles)
    band_position = bollinger_position(candles, 5)

    assert position.latest is not None and 0.0 <= position.latest <= 1.0
    assert high_distance.latest is not None and high_distance.latest >= 0
    assert low_distance.latest is not None and low_distance.latest >= 0
    assert weighted.latest is not None and weighted.latest > 0
    assert band_position.latest is not None


def test_trend_foundations_show_rising_market() -> None:
    candles = make_candles()
    relationship = ema_relationship(candles, 5, 10)
    slope = ema_slope(candles, 5, 3)
    distance = price_distance_from_ema(candles, 5)
    persistence = trend_persistence(candles, 5, 5)

    assert relationship.direction.latest == 1.0
    assert relationship.strength.latest is not None and relationship.strength.latest > 0
    assert slope.latest is not None and slope.latest > 0
    assert distance.latest is not None and distance.latest > 0
    assert persistence.latest == pytest.approx(1.0)


def test_volume_spike_rejects_non_positive_threshold() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        volume_spike(make_candles(), 5, threshold=0)
