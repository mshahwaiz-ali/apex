"""Provider-independent market-data contracts."""

from __future__ import annotations

from typing import Protocol

from apex.domain.models import Candle, TickerSnapshot
from apex.intelligence.contracts import FundingRateSnapshot, OpenInterestSnapshot


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


class DerivativesDataProvider(Protocol):
    """Optional public derivatives data contract."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    def fetch_funding_rate(self, symbol: str) -> FundingRateSnapshot:
        """Fetch the latest public funding-rate snapshot."""

    def fetch_open_interest(self, symbol: str) -> OpenInterestSnapshot:
        """Fetch the latest public open-interest snapshot."""
