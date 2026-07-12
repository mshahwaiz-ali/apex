"""Provider-independent candle caching decorator."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

from apex.data.cache.candles import CandleCacheKey, FileCandleCache
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import Candle, TickerSnapshot

DEFAULT_CANDLE_CACHE_TTLS: dict[str, timedelta] = {
    "1m": timedelta(seconds=10),
    "3m": timedelta(seconds=20),
    "5m": timedelta(seconds=30),
    "15m": timedelta(minutes=1),
    "30m": timedelta(minutes=2),
    "1h": timedelta(minutes=5),
    "4h": timedelta(minutes=15),
}


@dataclass(frozen=True, slots=True)
class CandleCachePolicy:
    """Freshness rules for cached candle requests."""

    time_to_live: Mapping[str, timedelta] = field(
        default_factory=lambda: DEFAULT_CANDLE_CACHE_TTLS.copy()
    )

    def __post_init__(self) -> None:
        for timeframe, duration in self.time_to_live.items():
            if not timeframe.strip():
                raise ValueError("cache policy timeframe cannot be empty")
            if duration < timedelta(0):
                raise ValueError(f"cache TTL cannot be negative for timeframe {timeframe}")

    def max_age_for(self, timeframe: str) -> timedelta | None:
        """Return cache freshness duration for a timeframe."""

        return self.time_to_live.get(timeframe.lower().strip())


class CachedMarketDataProvider:
    """Add transparent candle caching to any market-data provider."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: FileCandleCache,
        *,
        policy: CandleCachePolicy | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._policy = policy or CandleCachePolicy()

    @property
    def name(self) -> str:
        return self._provider.name

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Return fresh cached candles or fetch and best-effort cache live candles."""

        max_age = self._policy.max_age_for(timeframe)
        if max_age is None:
            return self._provider.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )

        key = CandleCacheKey(
            provider=self.name,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        cached = self._cache.load(key, max_age=max_age)
        if cached is not None:
            return list(cached.candles)

        candles = self._provider.fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        with contextlib.suppress(OSError):
            self._cache.save(key, candles)

        return candles

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Ticker snapshots remain live and bypass candle caching."""

        return self._provider.fetch_ticker(symbol)
