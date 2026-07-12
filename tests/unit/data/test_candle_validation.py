from datetime import UTC, datetime, timedelta

import pytest

from apex.data.validation import validate_candle_series
from apex.domain.models import Candle


def make_candle(
    *,
    open_time: datetime,
    timeframe: str = "15m",
    is_closed: bool = True,
) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15) - timedelta(milliseconds=1),
        open=100,
        high=110,
        low=95,
        close=105,
        volume=1000,
        is_closed=is_closed,
        source="test",
    )


def test_valid_candle_series_passes() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    candles = [
        make_candle(open_time=start),
        make_candle(open_time=start + timedelta(minutes=15)),
        make_candle(
            open_time=start + timedelta(minutes=30),
            is_closed=False,
        ),
    ]

    result = validate_candle_series(
        candles,
        expected_timeframe="15m",
        now=start + timedelta(minutes=35),
    )

    assert result.is_valid is True
    assert result.errors == ()


def test_duplicate_timestamp_is_rejected() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    candles = [
        make_candle(open_time=start),
        make_candle(open_time=start),
    ]

    result = validate_candle_series(
        candles,
        expected_timeframe="15m",
        now=start + timedelta(minutes=20),
    )

    assert result.is_valid is False
    assert any("duplicate candle" in error for error in result.errors)


def test_missing_interval_is_rejected() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    candles = [
        make_candle(open_time=start),
        make_candle(open_time=start + timedelta(minutes=30)),
    ]

    result = validate_candle_series(
        candles,
        expected_timeframe="15m",
        now=start + timedelta(minutes=35),
    )

    assert result.is_valid is False
    assert any("unexpected candle interval" in error for error in result.errors)


def test_stale_series_is_rejected() -> None:
    start = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)

    candles = [
        make_candle(open_time=start),
        make_candle(open_time=start + timedelta(minutes=15)),
    ]

    result = validate_candle_series(
        candles,
        expected_timeframe="15m",
        now=start + timedelta(hours=2),
    )

    assert result.is_valid is False
    assert "latest closed candle is stale" in result.errors


def test_active_candle_must_be_last() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    candles = [
        make_candle(open_time=start, is_closed=False),
        make_candle(open_time=start + timedelta(minutes=15)),
    ]

    result = validate_candle_series(
        candles,
        expected_timeframe="15m",
        now=start + timedelta(minutes=20),
    )

    assert result.is_valid is False
    assert "active candle must be the final candle" in result.errors


def test_validation_clock_must_be_timezone_aware() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="timezone-aware"):
        validate_candle_series(
            [make_candle(open_time=start)],
            expected_timeframe="15m",
            now=datetime(2026, 7, 12, 12, 20),
        )


def test_future_closed_candle_is_rejected() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    result = validate_candle_series(
        [make_candle(open_time=start)],
        expected_timeframe="15m",
        now=start + timedelta(minutes=5),
    )

    assert result.is_valid is False
    assert "candle 0 is marked closed before close_time" in result.errors


def test_expired_active_candle_is_rejected() -> None:
    start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    result = validate_candle_series(
        [make_candle(open_time=start, is_closed=False)],
        expected_timeframe="15m",
        now=start + timedelta(minutes=20),
    )

    assert result.is_valid is False
    assert "candle 0 is marked active after close_time" in result.errors
