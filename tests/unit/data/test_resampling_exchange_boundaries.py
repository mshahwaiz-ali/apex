from datetime import UTC, datetime, timedelta

from apex.data.resampling import resample_candles
from apex.domain.models import Candle


def test_resample_accepts_exchange_close_one_millisecond_before_boundary() -> None:
    start = datetime(2026, 7, 15, tzinfo=UTC)
    candles = []
    for index in range(6):
        open_time = start + timedelta(hours=4 * index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
                open=100.0 + index,
                high=102.0 + index,
                low=99.0 + index,
                close=101.0 + index,
                volume=1000.0 + index,
                is_closed=True,
                source="binance",
            )
        )

    result = resample_candles(
        candles,
        target_timeframe="12h",
        source_timeframe="4h",
    )

    assert len(result) == 2
    assert all(candle.is_closed for candle in result)
    assert result[0].open_time == start
    assert result[0].close_time == start + timedelta(hours=12)
