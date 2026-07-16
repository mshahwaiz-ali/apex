"""Application-level construction for market-data services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from apex.config import FileSettings
from apex.data.cache.candles import FileCandleCache
from apex.data.providers import (
    BinanceFuturesMarketDataProvider,
    BinanceFuturesUniverseProvider,
    CachedMarketDataProvider,
    ResamplingMarketDataProvider,
)
from apex.data.providers.cached_futures_universe import (
    CachedFuturesUniverseProvider,
)
from apex.data.providers.base import (
    FuturesMarketScreenerProvider,
    FuturesUniverseProvider,
    MarketDataProvider,
)


class ManagedMarketDataProvider(
    MarketDataProvider,
    FuturesMarketScreenerProvider,
    Protocol,
):
    """Live futures provider with screening and closable resources."""

    def close(self) -> None:
        """Release provider resources."""


class ManagedFuturesUniverseProvider(FuturesUniverseProvider, Protocol):
    """Futures-universe provider that owns closable runtime resources."""

    def close(self) -> None:
        """Release provider resources."""


ProviderBuilder = Callable[[], ManagedMarketDataProvider]
FuturesUniverseProviderBuilder = Callable[[], ManagedFuturesUniverseProvider]


@dataclass(slots=True)
class MarketDataServices:
    """Providers used by application commands during one execution scope."""

    candles: MarketDataProvider
    ticker: MarketDataProvider
    futures_screener: FuturesMarketScreenerProvider
    futures_universe: FuturesUniverseProvider
    _live_provider: ManagedMarketDataProvider
    _futures_universe_provider: ManagedFuturesUniverseProvider

    def close(self) -> None:
        """Close the underlying live provider once."""

        self._futures_universe_provider.close()
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
    futures_universe_provider_builder: FuturesUniverseProviderBuilder = (
        BinanceFuturesUniverseProvider
    ),
) -> MarketDataServices:
    """Build futures ticker and optionally cached futures candle providers."""

    builders = provider_builders or {"binance": BinanceFuturesMarketDataProvider}
    normalized_name = provider_name.lower().strip()

    try:
        live_provider = builders[normalized_name]()
    except KeyError as exc:
        supported = ", ".join(sorted(builders))
        raise ValueError(
            f"Unsupported market-data provider: {provider_name}. Supported: {supported}"
        ) from exc

    live_futures_universe_provider = futures_universe_provider_builder()
    futures_universe_provider: FuturesUniverseProvider = (
        live_futures_universe_provider
    )
    if settings.cache_enabled:
        futures_universe_provider = CachedFuturesUniverseProvider(
            live_futures_universe_provider,
            settings.data_dir
            / "cache"
            / "futures_universe"
            / "contracts.json",
            time_to_live=timedelta(
                seconds=(
                    settings
                    .futures_screener
                    .metadata_cache_ttl_seconds
                )
            ),
        )

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
        futures_screener=live_provider,
        futures_universe=futures_universe_provider,
        _live_provider=live_provider,
        _futures_universe_provider=live_futures_universe_provider,
    )
