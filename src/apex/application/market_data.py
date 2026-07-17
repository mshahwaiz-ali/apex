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
    Market