from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features import ActiveCandlePolicy
from apex.features.moving_averages import (
    exponential_moving_average,
    simple_moving_average,
)

START = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)


def make_candles(
    closes: list[float],
    *,
    active_final: bool = False,
) -> list[Candle]:
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
                high=close,
                low=close,
                close=close,
                volume=100.0,
                is_closed=not (active_final and index == len(closes) - 1),
                source="binance",
            )
        )
    return candles


def test_simple_moving_average_is_aligned_and_deterministic() -> None:
    result = simple_moving_average(make_candles([1, 2, 3, 4, 5]), 3)

    assert result.values == (None, None, 2.0, 3.0, 4.0)
    assert result.latest == 4.0
    assert result.spec.name == "sma_close_3"
    assert result.spec.minimum_candles == 3
    assert not result.spec.accepts_active_candle


def test_exponential_moving_average_uses_initial_sma_seed() -> None:
    result = exponential_moving_average(make_candles([1, 2, 3, 4, 5]), 3)

    assert result.values == (None, None, 2.0, 3.0, 4.0)
    assert result.latest == 4.0
    assert result.spec.name == "ema_close_3"


def test_exponential_moving_average_supports_period_one() -> None:
    result = exponential_moving_average(make_candles([2, 4, 8]), 1)

    assert result.values == (2.0, 4.0, 8.0)


def test_default_policy_drops_final_active_candle() -> None:
    result = simple_moving_average(make_candles([1, 2, 3, 100], active_final=True), 3)

    assert result.values == (None, None, 2.0)
    assert result.latest == 2.0


def test_allow_policy_includes_final_active_candle() -> None:
    result = simple_moving_average(
        make_candles([1, 2, 3, 4], active_final=True),
        3,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )

    assert result.values == (None, None, 2.0, 3.0)
    assert result.spec.accepts_active_candle


def test_reject_policy_rejects_final_active_candle() -> None:
    with pytest.raises(ValueError, match="active candle is not accepted"):
        exponential_moving_average(
            make_candles([1, 2, 3], active_final=True),
            2,
            active_candle_policy=ActiveCandlePolicy.REJECT,
        )


def test_active_candle_drop_can_make_series_too_short() -> None:
    with pytest.raises(ValueError, match="requires at least 3 usable candles"):
        simple_moving_average(make_candles([1, 2, 3], active_final=True), 3)


def test_moving_averages_reject_invalid_period() -> None:
    with pytest.raises(ValueError, match="period must be at least 1"):
        simple_moving_average(make_candles([1]), 0)
