from datetime import UTC, datetime

import pytest

from apex.data.validation import validate_candle_series
from apex.domain.models import Candle


def make_closed_candle() -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        close_time=datetime(2026, 7, 12, 10, 15, tzinfo=UTC),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=123.45,
        is_closed=True,
        source="binance",
    )


def test_can_skip_staleness_validation() -> None:
    result = validate_candle_series(
        [make_closed_candle()],
        expected_timeframe="15m",
        now=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
        max_staleness_intervals=None,
    )

    assert result.is_valid
    assert "latest closed candle is stale" not in result.errors


def test_rejects_negative_staleness_interval_limit() -> None:
    with pytest.raises(
        ValueError,
        match="max_staleness_intervals cannot be negative",
    ):
        validate_candle_series(
            [make_closed_candle()],
            expected_timeframe="15m",
            now=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
            max_staleness_intervals=-1,
        )
