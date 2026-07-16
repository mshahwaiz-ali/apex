"""Binance USDT-margined futures market-data provider."""

from __future__ import annotations

from apex.data.providers.binance import BinanceMarketDataProvider


class BinanceFuturesMarketDataProvider(BinanceMarketDataProvider):
    """Read-only Binance USDT-margined futures market-data adapter."""

    PROVIDER_NAME = "binance-futures"
    BASE_URL = "https://fapi.binance.com"
    CANDLES_PATH = "/fapi/v1/klines"
    BOOK_TICKER_PATH = "/fapi/v1/ticker/bookTicker"
    TICKER_24H_PATH = "/fapi/v1/ticker/24hr"
    ORDER_BOOK_PATH = "/fapi/v1/depth"
    EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"
