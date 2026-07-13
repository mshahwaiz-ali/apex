from datetime import UTC, datetime, timedelta

import pytest

from apex.data.providers.resampled import ResamplingMarketDataProvider
from apex.data.resampling import resample_candles, source_limit_for_resampling
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)

START = datetime(2026, 7, 13, tzinfo=UTC)


def _candle(
    index: int,
    *,
    timeframe: str = "1h",
    is_closed: bool = True,
    source: str = "fixture",
) -> Candle:
    open_time = START + timedelta(hours=index)
    base = 100.0 + index
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=base,
        high=base + 2.0,
        low=base - 1.0,
        close=base + 0.5,
        volume=10.0 + index,
        is_closed=is_closed,
        source=source,
    )


def test_resample_preserves_ohlcv_and_marks_source_timeframe() -> None:
    result = resample_candles(
        [_candle(index) for index in range(4)],
        target_timeframe="2h",
        source_timeframe="1h",
    )

    assert len(result) == 2
    first = result[0]
    assert first.timeframe == "2h"
    assert first.open_time == START
    assert first.close_time == START + timedelta(hours=2)
    assert first.open == 100.0
    assert first.high == 103.0
    assert first.low == 99.0
    assert first.close == 101.5
    assert first.volume == 21.0
    assert first.is_closed is True
    assert first.source == "resampled:1h:fixture"


def test_resample_marks_final_incomplete_bucket_active() -> None:
    result = resample_candles(
        [_candle(0), _candle(1), _candle(2, is_closed=False)],
        target_timeframe="2h",
        source_timeframe="1h",
    )

    assert [candle.is_closed for candle in result] == [True, False]
    assert result[-1].open_time == START + timedelta(hours=2)
    assert result[-1].close_time == START + timedelta(hours=4)


def test_resample_rejects_source_gaps() -> None:
    with pytest.raises(ValueError, match="interval gap"):
        resample_candles(
            [_candle(0), _candle(2)],
            target_timeframe="2h",
            source_timeframe="1h",
        )


def test_source_limit_for_resampling_is_bounded() -> None:
    assert (
        source_limit_for_resampling(
            target_timeframe="1D",
            source_timeframe="4h",
            target_limit=200,
            max_source_limit=1000,
        )
        == 1000
    )
    assert (
        source_limit_for_resampling(
            target_timeframe="2h",
            source_timeframe="1h",
            target_limit=3,
            max_source_limit=1000,
        )
        == 8
    )


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, int]] = []

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        self.requests.append((symbol, timeframe, limit))
        return [_candle(index, timeframe=timeframe, source=self.name) for index in range(limit)]

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=symbol,
            last_price=100.0,
            bid_price=99.5,
            ask_price=100.5,
            quote_volume_24h=1000.0,
            captured_at=START,
            source=self.name,
        )

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            symbol=symbol,
            bids=(OrderBookLevel(price=99.0, quantity=1.0),),
            asks=(OrderBookLevel(price=101.0, quantity=1.0),),
            captured_at=START,
            source=self.name,
        )

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        return ExchangeFilterSnapshot(
            symbol=symbol,
            tick_size=0.01,
            step_size=0.001,
            min_quantity=0.001,
            min_notional=5.0,
            captured_at=START,
            source=self.name,
        )


def test_resampling_provider_fetches_configured_source_timeframe() -> None:
    provider = FakeProvider()
    wrapped = ResamplingMarketDataProvider(
        provider,
        resampling_sources={"2h": "1h"},
    )

    candles = wrapped.fetch_candles("BTC/USDT", "2h", limit=2)

    assert provider.requests == [("BTC/USDT", "1h", 6)]
    assert [candle.timeframe for candle in candles] == ["2h", "2h"]


def test_resampling_provider_delegates_native_timeframes() -> None:
    provider = FakeProvider()
    wrapped = ResamplingMarketDataProvider(provider, resampling_sources={"2h": "1h"})

    candles = wrapped.fetch_candles("BTC/USDT", "1h", limit=2)

    assert provider.requests == [("BTC/USDT", "1h", 2)]
    assert [candle.timeframe for candle in candles] == ["1h", "1h"]


def test_resampling_provider_delegates_microstructure_snapshots() -> None:
    provider = FakeProvider()
    wrapped = ResamplingMarketDataProvider(provider, resampling_sources={"2h": "1h"})

    assert wrapped.fetch_order_book("BTC/USDT").source == "fake"
    assert wrapped.fetch_exchange_filters("BTC/USDT").min_notional == 5.0
