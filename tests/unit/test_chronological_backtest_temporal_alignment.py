from datetime import UTC, datetime, timedelta

from apex.application.chronological_backtest import (
    _has_required_warmup,
    _HistoricalPrefixProvider,
)
from apex.domain import Candle

START = datetime(2026, 1, 1, tzinfo=UTC)


def _candle(index: int, *, timeframe: str = "5m", is_closed: bool = True) -> Candle:
    open_time = START + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=5),
        open=100.0 + index,
        high=101.0 + index,
        low=99.0 + index,
        close=100.5 + index,
        volume=1000.0,
        is_closed=is_closed,
        source="fixture",
    )


def test_historical_provider_excludes_active_and_future_candles() -> None:
    candles = (
        *tuple(_candle(index) for index in range(4)),
        _candle(4, is_closed=False),
        _candle(5),
    )
    decision_time = candles[3].close_time
    provider = _HistoricalPrefixProvider({"5m": candles}, decision_time)

    available = provider.fetch_candles("BTC/USDT", "5m", limit=100)
    ticker = provider.fetch_ticker("BTC/USDT")

    assert available == list(candles[:4])
    assert ticker.last_price == candles[3].close
    assert ticker.captured_at == decision_time


def test_warmup_requires_enough_closed_candles_on_every_timeframe() -> None:
    five_minute = tuple(_candle(index) for index in range(40))
    fifteen_minute = (
        *tuple(_candle(index, timeframe="15m") for index in range(39)),
        _candle(39, timeframe="15m", is_closed=False),
    )
    decision_time = five_minute[-1].close_time
    provider = _HistoricalPrefixProvider(
        {"5m": five_minute, "15m": fifteen_minute},
        decision_time,
    )

    assert not _has_required_warmup(
        provider,
        "BTC/USDT",
        ("5m", "15m"),
        40,
    )
