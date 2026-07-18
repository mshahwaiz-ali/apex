"""Provider-independent market-data contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apex.domain.futures_evidence import (
    FundingRateSnapshot,
    OpenInterestSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import FuturesTickerSnapshot
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)


class MarketDataProvider(Protocol):
    """Contract implemented by every market-data provider."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch normalized OHLCV candles."""

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch normalized current-market ticker data."""


class HistoricalRangeMarketDataProvider(Protocol):
    """Optional provider contract for explicit historical time ranges."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_candles_range(
        self,
        symbol: str,
        timeframe: str,
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Candle]:
        """Fetch closed candles whose open times fall in ``[start_time, end_time)``."""


class FuturesUniverseProvider(Protocol):
    """Optional futures exchange-universe contract."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_futures_contracts(self) -> tuple[FuturesContractMetadata, ...]:
        """Fetch normalized futures exchange-contract metadata."""


class FuturesMarketScreenerProvider(Protocol):
    """Optional provider contract for market-wide futures ticker batches."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_futures_tickers(self) -> tuple[FuturesTickerSnapshot, ...]:
        """Fetch normalized market-wide futures ticker snapshots."""


class MarketMicrostructureProvider(Protocol):
    """Optional order-book and exchange-filter contract."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Fetch normalized current order-book depth."""

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        """Fetch normalized exchange precision and notional filters."""


class FuturesEvidenceProvider(Protocol):
    """Optional read-only derivatives participation contract."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_funding_rates(self, symbol: str, limit: int = 100) -> tuple[FundingRateSnapshot, ...]:
        """Fetch chronological funding observations."""

    def fetch_open_interest_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[OpenInterestSnapshot, ...]:
        """Fetch chronological open-interest observations."""

    def fetch_taker_flow_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[TakerFlowSnapshot, ...]:
        """Fetch chronological taker buy/sell observations."""
