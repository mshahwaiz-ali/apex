"""Provider-independent market-data contracts."""

from __future__ import annotations

from typing import Protocol

from apex.domain.models import Candle, TickerSnapshot


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
