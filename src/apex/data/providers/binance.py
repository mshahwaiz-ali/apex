"""Binance public market-data provider."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import RetryPolicy, request_json
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)


class BinanceMarketDataProvider:
    """Read-only Binance Spot market-data adapter."""

    PROVIDER_NAME = "binance"
    BASE_URL = "https://api.binance.com"
    CANDLES_PATH = "/api/v3/klines"
    BOOK_TICKER_PATH = "/api/v3/ticker/bookTicker"
    TICKER_24H_PATH = "/api/v3/ticker/24hr"
    ORDER_BOOK_PATH = "/api/v3/depth"
    EXCHANGE_INFO_PATH = "/api/v3/exchangeInfo"
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
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._owns_client = client is None
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "Apex-Trading-Agent/0.1"},
        )

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

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
        """Fetch and normalize Binance Spot candlesticks with backward pagination."""

        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            supported = ", ".join(sorted(self.SUPPORTED_TIMEFRAMES))
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {supported}")

        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")

        normalized_symbol = self._normalize_symbol(symbol)
        now = datetime.now(UTC)
        candles_by_open_time: dict[datetime, Candle] = {}
        end_time_ms: int | None = None

        while len(candles_by_open_time) < limit:
            page_limit = min(1000, limit - len(candles_by_open_time))
            params: dict[str, str | int] = {
                "symbol": normalized_symbol,
                "interval": timeframe,
                "limit": page_limit,
            }
            if end_time_ms is not None:
                params["endTime"] = end_time_ms

            payload = request_json(
                self._client,
                "GET",
                self.CANDLES_PATH,
                provider=self.name,
                operation="fetch candles",
                retry_policy=self._retry_policy,
                sleep=self._sleep,
                params=params,
            )
            if not isinstance(payload, list):
                raise ProviderResponseError(
                    "Binance candle response must be a list",
                    provider=self.name,
                    operation="fetch candles",
                )
            if not payload:
                break

            page = [
                self._parse_candle(
                    row=row,
                    display_symbol=symbol.upper(),
                    timeframe=timeframe,
                    now=now,
                )
                for row in payload
            ]
            page.sort(key=lambda candle: candle.open_time)

            for candle in page:
                candles_by_open_time[candle.open_time] = candle

            next_end_time_ms = int(page[0].open_time.timestamp() * 1000) - 1
            if end_time_ms is not None and next_end_time_ms >= end_time_ms:
                break
            if len(payload) < page_limit:
                break
            end_time_ms = next_end_time_ms

        candles = sorted(candles_by_open_time.values(), key=lambda candle: candle.open_time)

        if not candles:
            raise ProviderResponseError(
                "Binance returned no candles",
                provider=self.name,
                operation="fetch candles",
            )

        return candles[-limit:]

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch and normalize Binance Spot ticker data."""

        normalized_symbol = self._normalize_symbol(symbol)

        book_payload = request_json(
            self._client,
            "GET",
            self.BOOK_TICKER_PATH,
            provider=self.name,
            operation="fetch book ticker",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
            params={"symbol": normalized_symbol},
        )
        stats_payload = request_json(
            self._client,
            "GET",
            self.TICKER_24H_PATH,
            provider=self.name,
            operation="fetch 24h ticker",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
            params={"symbol": normalized_symbol},
        )

        if not isinstance(book_payload, dict):
            raise ProviderResponseError(
                "Binance book ticker response must be an object",
                provider=self.name,
                operation="fetch book ticker",
            )
        if not isinstance(stats_payload, dict):
            raise ProviderResponseError(
                "Binance 24h ticker response must be an object",
                provider=self.name,
                operation="fetch 24h ticker",
            )

        try:
            return TickerSnapshot(
                symbol=symbol.upper(),
                last_price=float(stats_payload["lastPrice"]),
                bid_price=float(book_payload["bidPrice"]),
                ask_price=float(book_payload["askPrice"]),
                quote_volume_24h=float(stats_payload["quoteVolume"]),
                captured_at=datetime.now(UTC),
                source=self.name,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance ticker response fields",
                provider=self.name,
                operation="parse ticker",
            ) from exc

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Fetch and normalize Binance Spot order-book depth."""

        if not 1 <= depth <= 5000:
            raise ValueError("order-book depth must be between 1 and 5000")
        normalized_symbol = self._normalize_symbol(symbol)
        payload = request_json(
            self._client,
            "GET",
            self.ORDER_BOOK_PATH,
            provider=self.name,
            operation="fetch order book",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
            params={"symbol": normalized_symbol, "limit": depth},
        )
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Binance order book response must be an object",
                provider=self.name,
                operation="fetch order book",
            )
        try:
            bids = tuple(self._parse_order_book_level(row) for row in payload["bids"])
            asks = tuple(self._parse_order_book_level(row) for row in payload["asks"])
            return OrderBookSnapshot(
                symbol=symbol.upper(),
                bids=bids,
                asks=asks,
                captured_at=datetime.now(UTC),
                source=self.name,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance order book response fields",
                provider=self.name,
                operation="parse order book",
            ) from exc

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        """Fetch and normalize Binance Spot exchange precision filters."""

        normalized_symbol = self._normalize_symbol(symbol)
        payload = request_json(
            self._client,
            "GET",
            self.EXCHANGE_INFO_PATH,
            provider=self.name,
            operation="fetch exchange filters",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
            params={"symbol": normalized_symbol},
        )
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Binance exchange info response must be an object",
                provider=self.name,
                operation="fetch exchange filters",
            )
        try:
            symbols = payload["symbols"]
            if not isinstance(symbols, list) or not symbols:
                raise ValueError("missing symbol filters")
            filters = {
                item["filterType"]: item
                for item in symbols[0]["filters"]
                if isinstance(item, dict) and "filterType" in item
            }
            price_filter = filters["PRICE_FILTER"]
            lot_filter = filters["LOT_SIZE"]
            notional_filter = filters.get("MIN_NOTIONAL") or filters["NOTIONAL"]
            notional_value = notional_filter.get(
                "minNotional",
                notional_filter.get("notional"),
            )
            if notional_value is None:
                raise KeyError("minNotional")
            return ExchangeFilterSnapshot(
                symbol=symbol.upper(),
                tick_size=float(price_filter["tickSize"]),
                step_size=float(lot_filter["stepSize"]),
                min_quantity=float(lot_filter["minQty"]),
                min_notional=float(notional_value),
                captured_at=datetime.now(UTC),
                source=self.name,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance exchange filter response fields",
                provider=self.name,
                operation="parse exchange filters",
            ) from exc

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
            raise ProviderResponseError(
                "Invalid Binance candle row",
                provider=self.name,
                operation="parse candles",
            )

        try:
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
        except ProviderResponseError:
            raise
        except (IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance candle values",
                provider=self.name,
                operation="parse candles",
            ) from exc

    @staticmethod
    def _parse_order_book_level(row: Any) -> OrderBookLevel:
        if not isinstance(row, list | tuple) or len(row) < 2:
            raise ValueError("invalid order book level")
        return OrderBookLevel(price=float(row[0]), quantity=float(row[1]))

    @classmethod
    def _milliseconds_to_datetime(cls, value: Any) -> datetime:
        try:
            milliseconds = int(value)
            return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
        except (OSError, OverflowError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                f"Invalid Binance timestamp: {value!r}",
                provider=cls.PROVIDER_NAME,
                operation="parse candles",
            ) from exc
