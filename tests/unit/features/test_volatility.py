from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features import ActiveCandlePolicy
from apex.features.volatility import (
    atr_percentage,
    average_true_range,
    bollinger_bands,
    candle_range_ratio,
    true_range,
    wick_statistics,
)

START = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)


def make_candles(closes: list[float], *, active_final: bool = False) -> list[Candle]:
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = START + timedelta(minutes=15 * index)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=15),
                open=close - 1,
                high=close + 2,
                low=close - 3,
                close=close,
                volume=100 + index,
                is_closed=not (active_final and index == len(closes) - 1),
                source="test",
            )
        )
    return candles


def test_true_range_uses_previous_close() -> None:
    candles = make_candles([100, 110])
    result = true_range(candles)
    assert result.values == (5.0, 12.0)


def test_atr_uses_wilder_smoothing() -> None:
    result = average_true_range(make_candles([100, 110, 108, 120]), period=3)
    assert result.values[:2] == (None, None)
    assert result.values[2] == pytest.approx((5 + 12 + 5) / 3)
    assert result.values[3] == pytest.approx((((5 + 12 + 5) / 3) * 2 + 14) / 3)


def test_atr_percentage_is_aligned() -> None:
    result = atr_percentage(make_candles([100, 110, 108]), period=2)
    assert result.values[0] is None
    assert result.values[1] == pytest.approx(((5 + 12) / 2) / 110 * 100)


def test_bollinger_bands_use_population_deviation() -> None:
    bands = bollinger_bands(make_candles([101, 102, 103]), period=3, standard_deviations=2)
    assert bands.middle.values == (None, None, 102.0)
    assert bands.upper.latest == pytest.approx(102 + 2 * (2 / 3) ** 0.5)
    assert bands.lower.latest == pytest.approx(102 - 2 * (2 / 3) ** 0.5)
    assert bands.width.latest is not None


def test_candle_range_ratio_is_one_for_equal_ranges() -> None:
    result = candle_range_ratio(make_candles([100, 101, 102]), period=2)
    assert result.values == (None, 1.0, 1.0)


def test_wick_statistics_are_normalized() -> None:
    candle = make_candles([100])[0]
    stats = wick_statistics(candle)
    assert stats.upper_ratio == pytest.approx(0.4)
    assert stats.lower_ratio == pytest.approx(0.4)
    assert stats.body_ratio == pytest.approx(0.2)


def test_default_policy_drops_active_final_candle() -> None:
    result = true_range(make_candles([100, 101], active_final=True))
    assert len(result.values) == 1


def test_allow_policy_keeps_active_final_candle() -> None:
    result = true_range(
        make_candles([100, 101], active_final=True),
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    assert len(result.values) == 2


def test_rejects_invalid_bollinger_multiplier() -> None:
    with pytest.raises(ValueError, match="positive finite"):
        bollinger_bands(make_candles([101, 102, 103]), period=3, standard_deviations=0)
