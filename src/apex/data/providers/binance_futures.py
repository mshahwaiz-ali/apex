"""Binance USDT-margined futures market-data provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from apex.data.providers.binance import BinanceMarketDataProvider
from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import request_json
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

        for exchange_symbol in sorted(
            books.keys() & statistics.keys()
        ):
            book = books[exchange_symbol]
            statistic = statistics[exchange_symbol]

            try:
                snapshot = FuturesTickerSnapshot(
                    symbol=exchange_symbol,
                    exchange_symbol=exchange_symbol,
                    last_price=float(statistic["last_price"]),
                    bid_price=float(book["bid_price"]),
                    ask_price=float(book["ask_price"]),
                    quote_volume_24h=float(
                        statistic["quote_volume_24h"]
                    ),
                    price_change_percentage_24h=float(
                        statistic[
                            "price_change_percentage_24h"
                        ]
                    ),
                    high_price_24h=self._optional_float(
                        statistic.get("high_price_24h")
                    ),
                    low_price_24h=self._optional_float(
                        statistic.get("low_price_24h")
                    ),
                    trade_count_24h=self._optional_int(
                        statistic.get("trade_count_24h")
                    ),
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
            exchange_symbol = cls._normalize_symbol(
                str(value["symbol"])
            )
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
            exchange_symbol = cls._normalize_symbol(
                str(value["symbol"])
            )
            parsed: dict[str, float | int] = {
                "last_price": float(value["lastPrice"]),
                "quote_volume_24h": float(
                    value["quoteVolume"]
                ),
                "price_change_percentage_24h": float(
                    value["priceChangePercent"]
                ),
            }

            high_price = cls._optional_float(
                value.get("highPrice")
            )
            low_price = cls._optional_float(
                value.get("lowPrice")
            )
            trade_count = cls._optional_int(
                value.get("count")
            )
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
