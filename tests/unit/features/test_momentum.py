from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features.momentum import macd, rate_of_change, relative_strength_index, rsi_slope

START = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)


def make_candles(closes: list[float]) -> list[Candle]:
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = START + timedelta(minutes=15 * index)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=15),
                open=close,
                high=close + 0.5,
                low=max(close - 0.5, 0.1),
                close=close,
                volume=100,
                is_closed=True,
                source="test",
            )
        )
    return candles


def test_rsi_all_gains_is_one_hundred() -> None:
    result = relative_strength_index(make_candles([1, 2, 3, 4]), period=3)
    assert result.values == (None, None, None, 100.0)


def test_rsi_all_losses_is_zero() -> None:
    result = relative_strength_index(make_candles([4, 3, 2, 1]), period=3)
    assert result.latest == 0.0


def test_rsi_flat_market_is_neutral() -> None:
    result = relative_strength_index(make_candles([5, 5, 5]), period=2)
    assert result.latest == 50.0


def test_rsi_slope_is_per_candle_change() -> None:
    result = rsi_slope(make_candles([1, 2, 3, 2, 3, 4, 5]), period=2, lookback=2)
    assert result.values[:4] == (None, None, None, None)
    assert result.latest is not None


def test_rate_of_change_is_percentage() -> None:
    result = rate_of_change(make_candles([100, 105, 110]), period=2)
    assert result.values == (None, None, 10.0)


def test_macd_is_aligned_and_histogram_matches_difference() -> None:
    result = macd(make_candles([float(value) for value in range(1, 12)]), 3, 5, 2)
    assert len(result.macd.values) == 11
    assert result.macd.values[:4] == (None, None, None, None)
    assert result.signal.values[:5] == (None, None, None, None, None)
    assert result.histogram.latest == pytest.approx(
        result.macd.latest - result.signal.latest  # type: ignore[operator]
    )


def test_macd_rejects_invalid_period_order() -> None:
    with pytest.raises(ValueError, match="fast_period"):
        macd(make_candles([1, 2, 3, 4]), fast_period=3, slow_period=3, signal_period=1)
