from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from apex.domain import Candle


def test_candle_accepts_valid_ohlcv() -> None:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=12.5,
        is_closed=True,
        source="fixture",
    )
    assert candle.high == 102.0


def test_candle_rejects_invalid_high() -> None:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Candle(
            symbol="BTC/USDT",
            timeframe="1m",
            open_time=opened,
            close_time=opened + timedelta(minutes=1),
            open=100.0,
            high=99.0,
            low=98.0,
            close=101.0,
            volume=1.0,
            is_closed=True,
            source="fixture",
        )
