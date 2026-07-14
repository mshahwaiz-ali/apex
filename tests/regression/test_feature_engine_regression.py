import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.domain.models import Candle
from apex.features.momentum import relative_strength_index
from apex.features.moving_averages import exponential_moving_average, simple_moving_average
from apex.features.price_location import recent_range_position, vwap
from apex.features.volatility import average_true_range

FIXTURE = Path(__file__).parents[1] / "fixtures" / "feature_regression.json"
START = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)


def test_feature_engine_matches_deterministic_fixture() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candles = [_make_candle(index, close) for index, close in enumerate(payload["closes"])]
    expected = payload["expected"]

    assert simple_moving_average(candles, 5).latest == pytest.approx(expected["sma_5"])
    assert exponential_moving_average(candles, 5).latest == pytest.approx(expected["ema_5"])
    assert average_true_range(candles, 5).latest == pytest.approx(expected["atr_5"])
    assert relative_strength_index(candles, 5).latest == pytest.approx(expected["rsi_5"])
    assert vwap(candles).latest == pytest.approx(expected["vwap"])
    assert recent_range_position(candles, 5).latest == pytest.approx(
        expected["recent_range_position_5"]
    )


def _make_candle(index: int, close: float) -> Candle:
    open_time = START + timedelta(minutes=15 * index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15),
        open=close - 0.5,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1.0,
        is_closed=True,
        source="fixture",
    )
