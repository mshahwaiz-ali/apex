"""Binance public market-data provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from apex.domain.models import Candle, TickerSnapshot


class BinanceMarketDataProvider:
    """Read-only Binance Spot market-data adapter."""

    BASE_URL = "https://api.binance.com"
    SUPPORTED_TIMEFRAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "4h",
        }
    )

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "Apex-Trading-Agent/0.1"},
        )

    @property
    def name(self) -> str:
        return "binance"

    def close(self) -> None:
        """Close the internally managed HTTP client."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> BinanceMarketDataProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch and normalize Binance Spot candlesticks."""

        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            supported = ", ".join(sorted(self.SUPPORTED_TIMEFRAMES))
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {supported}")

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        normalized_symbol = self._normalize_symbol(symbol)

        response = self._client.get(
            "/api/v3/klines",
            params={
                "symbol": normalized_symbol,
                "interval": timeframe,
                "limit": limit,
            },
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Binance candle response must be a list")

        now = datetime.now(UTC)
        candles = [
            self._parse_candle(
                row=row,
                display_symbol=symbol.upper(),
                timeframe=timeframe,
                now=now,
            )
            for row in payload
        ]

        if not candles:
            raise ValueError("Binance returned no candles")

        return candles

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch and normalize Binance Spot ticker data."""

        normalized_symbol = self._normalize_symbol(symbol)

        book_response = self._client.get(
            "/api/v3/ticker/bookTicker",
            params={"symbol": normalized_symbol},
        )
        book_response.raise_for_status()

        stats_response = self._client.get(
            "/api/v3/ticker/24hr",
            params={"symbol": normalized_symbol},
        )
        stats_response.raise_for_status()

        book_payload = book_response.json()
        stats_payload = stats_response.json()

        if not isinstance(book_payload, dict):
            raise ValueError("Binance book ticker response must be an object")
        if not isinstance(stats_payload, dict):
            raise ValueError("Binance 24h ticker response must be an object")

        return TickerSnapshot(
            symbol=symbol.upper(),
            last_price=float(stats_payload["lastPrice"]),
            bid_price=float(book_payload["bidPrice"]),
            ask_price=float(book_payload["askPrice"]),
            quote_volume_24h=float(stats_payload["quoteVolume"]),
            captured_at=datetime.now(UTC),
            source=self.name,
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.upper().replace("/", "").replace("-", "").strip()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        return normalized

    def _parse_candle(
        self,
        *,
        row: Any,
        display_symbol: str,
        timeframe: str,
        now: datetime,
    ) -> Candle:
        if not isinstance(row, list) or len(row) < 7:
            raise ValueError("Invalid Binance candle row")

        open_time = self._milliseconds_to_datetime(row[0])
        close_time = self._milliseconds_to_datetime(row[6])

        return Candle(
            symbol=display_symbol,
            timeframe=timeframe,
            open_time=open_time,
            close_time=close_time,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            is_closed=close_time <= now,
            source=self.name,
        )

    @staticmethod
    def _milliseconds_to_datetime(value: Any) -> datetime:
        try:
            milliseconds = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid Binance timestamp: {value!r}") from exc

        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
