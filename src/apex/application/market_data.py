"""Application-level construction for market-data services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from apex.config import FileSettings
from apex.data.cache.candles import FileCandleCache
from apex.data.providers import (
    BinanceMarketDataProvider,
    CachedMarketDataProvider,
    ResamplingMarketDataProvider,
)
from apex.data.providers.base import MarketDataProvider


class ManagedMarketDataProvider(MarketDataProvider, Protocol):
    """Market-data provider that owns closable runtime resources."""

    def close(self) -> None:
        """Release provider resources."""


ProviderBuilder = Callable[[], ManagedMarketDataProvider]


@dataclass(slots=True)
class MarketDataServices:
    """Providers used by application commands during one execution scope."""

    candles: MarketDataProvider
    ticker: MarketDataProvider
    _live_provider: ManagedMarketDataProvider

    def close(self) -> None:
        """Close the underlying live provider once."""

        self._live_provider.close()

    def __enter__(self) -> MarketDataServices:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def create_market_data_services(
    settings: FileSettings,
    *,
    provider_name: str = "binance",
    provider_builders: dict[str, ProviderBuilder] | None = None,
) -> MarketDataServices:
    """Build live ticker and optionally cached candle providers."""

    builders = provider_builders or {"binance": BinanceMarketDataProvider}
    normalized_name = provider_name.lower().strip()

    try:
        live_provider = builders[normalized_name]()
    except KeyError as exc:
        supported = ", ".join(sorted(builders))
        raise ValueError(
            f"Unsupported market-data provider: {provider_name}. Supported: {supported}"
        ) from exc

    candle_provider: MarketDataProvider = live_provider
    if settings.cache_enabled:
        cache = FileCandleCache(settings.data_dir / "cache" / "candles")
        candle_provider = CachedMarketDataProvider(live_provider, cache)
    if settings.timeframe_resampling_sources:
        candle_provider = ResamplingMarketDataProvider(
            candle_provider,
            resampling_sources=settings.timeframe_resampling_sources,
        )

    return MarketDataServices(
        candles=candle_provider,
        ticker=live_provider,
        _live_provider=live_provider,
    )
