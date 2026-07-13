"""Market-data provider decorator for configured candle resampling."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from apex.data.providers.base import MarketDataProvider, MarketMicrostructureProvider
from apex.data.resampling import resample_candles, source_limit_for_resampling
from apex.domain.models import Candle, ExchangeFilterSnapshot, OrderBookSnapshot, TickerSnapshot


class ResamplingMarketDataProvider:
    """Add deterministic higher-timeframe candle resampling to a provider."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        resampling_sources: Mapping[str, str],
        max_source_limit: int = 1000,
    ) -> None:
        if max_source_limit < 1:
            raise ValueError("max source limit must be at least one")
        self._provider = provider
        self._resampling_sources = {
            target.strip(): source.strip()
            for target, source in resampling_sources.items()
            if target.strip() and source.strip()
        }
        self._max_source_limit = max_source_limit

    @property
    def name(self) -> str:
        return self._provider.name

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch native candles or resample from a configured source timeframe."""

        source_timeframe = self._resampling_sources.get(timeframe)
        if source_timeframe is None:
            return self._provider.fetch_candles(symbol=symbol, timeframe=timeframe, limit=limit)

        source_limit = source_limit_for_resampling(
            target_timeframe=timeframe,
            source_timeframe=source_timeframe,
            target_limit=limit,
            max_source_limit=self._max_source_limit,
        )
        source_candles = self._provider.fetch_candles(
            symbol=symbol,
            timeframe=source_timeframe,
            limit=source_limit,
        )
        return resample_candles(
            source_candles,
            target_timeframe=timeframe,
            source_timeframe=source_timeframe,
            limit=limit,
        )

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Ticker snapshots are delegated unchanged."""

        return self._provider.fetch_ticker(symbol)

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Order-book snapshots are delegated unchanged."""

        provider = cast(MarketMicrostructureProvider, self._provider)
        return provider.fetch_order_book(symbol, depth=depth)

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        """Exchange filters are delegated unchanged."""

        provider = cast(MarketMicrostructureProvider, self._provider)
        return provider.fetch_exchange_filters(symbol)
