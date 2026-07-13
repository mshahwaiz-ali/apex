from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.data.cache.candles import FileCandleCache
from apex.data.providers.cached import (
    CachedMarketDataProvider,
    CandleCachePolicy,
)
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


class FakeMarketDataProvider:
    name = "fake"

    def __init__(self) -> None:
        self.candle_calls = 0
        self.ticker_calls = 0
        self.order_book_calls = 0
        self.exchange_filter_calls = 0

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        self.candle_calls += 1
        return [
            Candle(
                symbol=symbol.upper(),
                timeframe=timeframe,
                open_time=datetime(2026, 7, 12, 11, 30, tzinfo=UTC),
                close_time=datetime(2026, 7, 12, 11, 45, tzinfo=UTC),
                open=100.0,
                high=110.0,
                low=95.0,
                close=105.0,
                volume=123.45,
                is_closed=True,
                source=self.name,
            )
        ][:limit]

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        self.ticker_calls += 1
        return TickerSnapshot(
            symbol=symbol.upper(),
            last_price=105.0,
            bid_price=104.0,
            ask_price=106.0,
            quote_volume_24h=1_000_000.0,
            captured_at=NOW,
            source=self.name,
        )

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        self.order_book_calls += 1
        return OrderBookSnapshot(
            symbol=symbol.upper(),
            bids=(OrderBookLevel(price=104.0, quantity=1.0),),
            asks=(OrderBookLevel(price=106.0, quantity=1.0),),
            captured_at=NOW,
            source=self.name,
        )

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        self.exchange_filter_calls += 1
        return ExchangeFilterSnapshot(
            symbol=symbol.upper(),
            tick_size=0.01,
            step_size=0.001,
            min_quantity=0.001,
            min_notional=5.0,
            captured_at=NOW,
            source=self.name,
        )


def test_returns_cached_candles_without_second_provider_call(
    tmp_path: Path,
) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    first = cached_provider.fetch_candles("BTC/USDT", "15m", limit=1)
    second = cached_provider.fetch_candles("BTC/USDT", "15m", limit=1)

    assert first == second
    assert provider.candle_calls == 1


def test_refreshes_stale_cached_candles(tmp_path: Path) -> None:
    current_time = NOW

    def clock() -> datetime:
        return current_time

    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=clock)
    cached_provider = CachedMarketDataProvider(provider, cache)

    cached_provider.fetch_candles("BTC/USDT", "15m", limit=1)
    current_time = NOW + timedelta(minutes=2)
    cached_provider.fetch_candles("BTC/USDT", "15m", limit=1)

    assert provider.candle_calls == 2


def test_cache_keys_separate_limits(tmp_path: Path) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    cached_provider.fetch_candles("BTC/USDT", "15m", limit=1)
    cached_provider.fetch_candles("BTC/USDT", "15m", limit=2)

    assert provider.candle_calls == 2


def test_unsupported_policy_timeframe_bypasses_cache(
    tmp_path: Path,
) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    policy = CandleCachePolicy(time_to_live={"15m": timedelta(minutes=1)})
    cached_provider = CachedMarketDataProvider(
        provider,
        cache,
        policy=policy,
    )

    cached_provider.fetch_candles("BTC/USDT", "1h", limit=1)
    cached_provider.fetch_candles("BTC/USDT", "1h", limit=1)

    assert provider.candle_calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_ticker_always_bypasses_candle_cache(tmp_path: Path) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    cached_provider.fetch_ticker("BTC/USDT")
    cached_provider.fetch_ticker("BTC/USDT")

    assert provider.ticker_calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_microstructure_bypasses_candle_cache(tmp_path: Path) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    cached_provider.fetch_order_book("BTC/USDT")
    cached_provider.fetch_exchange_filters("BTC/USDT")

    assert provider.order_book_calls == 1
    assert provider.exchange_filter_calls == 1
    assert list(tmp_path.glob("*.json")) == []


def test_default_cache_freshness_rules() -> None:
    policy = CandleCachePolicy()

    assert policy.max_age_for("1m") == timedelta(seconds=10)
    assert policy.max_age_for("3m") == timedelta(seconds=20)
    assert policy.max_age_for("5m") == timedelta(seconds=30)
    assert policy.max_age_for("15m") == timedelta(minutes=1)
    assert policy.max_age_for("30m") == timedelta(minutes=2)
    assert policy.max_age_for("1h") == timedelta(minutes=5)
    assert policy.max_age_for("4h") == timedelta(minutes=15)
    assert policy.max_age_for("1d") is None


def test_cache_write_oserror_does_not_discard_live_candles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    def fail_save(*args, **kwargs) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(cache, "save", fail_save)

    candles = cached_provider.fetch_candles(
        "BTC/USDT",
        "15m",
        limit=1,
    )

    assert len(candles) == 1
    assert provider.candle_calls == 1
    assert list(tmp_path.glob("*.json")) == []


def test_cache_validation_error_is_not_suppressed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = FakeMarketDataProvider()
    cache = FileCandleCache(tmp_path, now=lambda: NOW)
    cached_provider = CachedMarketDataProvider(provider, cache)

    def fail_save(*args, **kwargs) -> None:
        raise ValueError("invalid candle series")

    monkeypatch.setattr(cache, "save", fail_save)

    import pytest

    with pytest.raises(ValueError, match="invalid candle series"):
        cached_provider.fetch_candles(
            "BTC/USDT",
            "15m",
            limit=1,
        )
