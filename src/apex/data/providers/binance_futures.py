"""Binance USDT-margined futures market-data provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from apex.data.providers.binance import BinanceMarketDataProvider
from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import request_json
from apex.domain.futures_evidence import (
    FundingRateSnapshot,
    OpenInterestSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.futures_screening import FuturesTickerSnapshot

TickerRowParser = Callable[
    [Any],
    tuple[str, dict[str, float | int]] | None,
]


class BinanceFuturesMarketDataProvider(BinanceMarketDataProvider):
    """Read-only Binance USDT-margined futures market-data adapter."""

    PROVIDER_NAME = "binance-futures"
    BASE_URL = "https://fapi.binance.com"
    CANDLES_PATH = "/fapi/v1/klines"
    BOOK_TICKER_PATH = "/fapi/v1/ticker/bookTicker"
    TICKER_24H_PATH = "/fapi/v1/ticker/24hr"
    ORDER_BOOK_PATH = "/fapi/v1/depth"
    EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"
    FUNDING_RATE_PATH = "/fapi/v1/fundingRate"
    OPEN_INTEREST_HISTORY_PATH = "/futures/data/openInterestHist"
    TAKER_FLOW_HISTORY_PATH = "/futures/data/takerlongshortRatio"

    def fetch_funding_rates(self, symbol: str, limit: int = 100) -> tuple[FundingRateSnapshot, ...]:
        payload = self._fetch_evidence_rows(
            self.FUNDING_RATE_PATH,
            symbol,
            limit,
            operation="fetch funding rates",
        )
        return tuple(
            FundingRateSnapshot(
                symbol=symbol.upper(),
                funding_rate=float(row["fundingRate"]),
                funding_time=datetime.fromtimestamp(int(row["fundingTime"]) / 1000, tz=UTC),
                source=self.name,
            )
            for row in payload
        )

    def fetch_open_interest_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[OpenInterestSnapshot, ...]:
        payload = self._fetch_evidence_rows(
            self.OPEN_INTEREST_HISTORY_PATH,
            symbol,
            limit,
            period=period,
            operation="fetch open-interest history",
        )
        return tuple(
            OpenInterestSnapshot(
                symbol=symbol.upper(),
                period=period,
                open_interest=float(row["sumOpenInterest"]),
                open_interest_value=float(row["sumOpenInterestValue"]),
                captured_at=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC),
                source=self.name,
            )
            for row in payload
        )

    def fetch_taker_flow_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[TakerFlowSnapshot, ...]:
        payload = self._fetch_evidence_rows(
            self.TAKER_FLOW_HISTORY_PATH,
            symbol,
            limit,
            period=period,
            operation="fetch taker-flow history",
        )
        return tuple(
            TakerFlowSnapshot(
                symbol=symbol.upper(),
                period=period,
                buy_volume=float(row["buyVol"]),
                sell_volume=float(row["sellVol"]),
                buy_sell_ratio=float(row["buySellRatio"]),
                captured_at=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC),
                source=self.name,
            )
            for row in payload
        )

    def _fetch_evidence_rows(
        self,
        path: str,
        symbol: str,
        limit: int,
        *,
        operation: str,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("futures evidence limit must be between 1 and 500")
        params: dict[str, str | int] = {
            "symbol": self._normalize_symbol(symbol),
            "limit": limit,
        }
        if period is not None:
            params["period"] = period
        payload = request_json(
            self._client,
            "GET",
            path,
            provider=self.name,
            operation=operation,
            retry_policy=self._retry_policy,
            sleep=self._sleep,
            params=params,
        )
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise ProviderResponseError(
                f"Binance {operation} response must be a list of objects",
                provider=self.name,
                operation=operation,
            )
        return sorted(payload, key=lambda row: int(row.get("timestamp", row.get("fundingTime", 0))))

    def fetch_futures_tickers(self) -> tuple[FuturesTickerSnapshot, ...]:
        """Fetch and join Binance market-wide futures ticker batches."""

        book_payload = request_json(
            self._client,
            "GET",
            self.BOOK_TICKER_PATH,
            provider=self.name,
            operation="fetch futures book tickers",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
        )
        stats_payload = request_json(
            self._client,
            "GET",
            self.TICKER_24H_PATH,
            provider=self.name,
            operation="fetch futures 24h tickers",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
        )

        if not isinstance(book_payload, list):
            raise ProviderResponseError(
                "Binance futures book ticker response must be a list",
                provider=self.name,
                operation="fetch futures book tickers",
            )

        if not isinstance(stats_payload, list):
            raise ProviderResponseError(
                "Binance futures 24h ticker response must be a list",
                provider=self.name,
                operation="fetch futures 24h tickers",
            )

        books = self._index_valid_rows(
            book_payload,
            self._parse_book_ticker_row,
        )
        statistics = self._index_valid_rows(
            stats_payload,
            self._parse_24h_ticker_row,
        )
        captured_at = datetime.now(UTC)

        snapshots: list[FuturesTickerSnapshot] = []

        for exchange_symbol in sorted(books.keys() & statistics.keys()):
            book = books[exchange_symbol]
            statistic = statistics[exchange_symbol]

            try:
                snapshot = FuturesTickerSnapshot(
                    symbol=exchange_symbol,
                    exchange_symbol=exchange_symbol,
                    last_price=float(statistic["last_price"]),
                    bid_price=float(book["bid_price"]),
                    ask_price=float(book["ask_price"]),
                    quote_volume_24h=float(statistic["quote_volume_24h"]),
                    price_change_percentage_24h=float(statistic["price_change_percentage_24h"]),
                    high_price_24h=self._optional_float(statistic.get("high_price_24h")),
                    low_price_24h=self._optional_float(statistic.get("low_price_24h")),
                    trade_count_24h=self._optional_int(statistic.get("trade_count_24h")),
                    captured_at=captured_at,
                    source=self.name,
                )
            except (TypeError, ValueError):
                continue

            snapshots.append(snapshot)

        return tuple(snapshots)

    @staticmethod
    def _index_valid_rows(
        rows: list[Any],
        parser: TickerRowParser,
    ) -> dict[str, dict[str, float | int]]:
        indexed: dict[str, dict[str, float | int]] = {}

        for row in rows:
            parsed = parser(row)
            if parsed is None:
                continue

            exchange_symbol, values = parsed
            indexed[exchange_symbol] = values

        return indexed

    @classmethod
    def _parse_book_ticker_row(
        cls,
        value: Any,
    ) -> tuple[str, dict[str, float | int]] | None:
        if not isinstance(value, dict):
            return None

        try:
            exchange_symbol = cls._normalize_symbol(str(value["symbol"]))
            bid_price = float(value["bidPrice"])
            ask_price = float(value["askPrice"])
        except (KeyError, TypeError, ValueError):
            return None

        return (
            exchange_symbol,
            {
                "bid_price": bid_price,
                "ask_price": ask_price,
            },
        )

    @classmethod
    def _parse_24h_ticker_row(
        cls,
        value: Any,
    ) -> tuple[str, dict[str, float | int]] | None:
        if not isinstance(value, dict):
            return None

        try:
            exchange_symbol = cls._normalize_symbol(str(value["symbol"]))
            parsed: dict[str, float | int] = {
                "last_price": float(value["lastPrice"]),
                "quote_volume_24h": float(value["quoteVolume"]),
                "price_change_percentage_24h": float(value["priceChangePercent"]),
            }

            high_price = cls._optional_float(value.get("highPrice"))
            low_price = cls._optional_float(value.get("lowPrice"))
            trade_count = cls._optional_int(value.get("count"))
        except (KeyError, TypeError, ValueError):
            return None

        if high_price is not None:
            parsed["high_price_24h"] = high_price

        if low_price is not None:
            parsed["low_price_24h"] = low_price

        if trade_count is not None:
            parsed["trade_count_24h"] = trade_count

        return exchange_symbol, parsed

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None

        return float(value)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None

        return int(value)
