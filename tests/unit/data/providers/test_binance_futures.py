"""Tests for Binance futures market-data endpoints."""

from datetime import UTC, datetime

import httpx

from apex.data.providers.binance_futures import BinanceFuturesMarketDataProvider


def test_fetch_candles_uses_futures_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fapi/v1/klines"
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "5m"
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200,
            json=[
                [
                    1_700_000_000_000,
                    "100.0",
                    "110.0",
                    "95.0",
                    "105.0",
                    "123.45",
                    1_700_000_299_999,
                ]
            ],
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    candles = provider.fetch_candles("BTC/USDT", "5m", limit=1)

    assert len(candles) == 1
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].source == "binance-futures"
    assert candles[0].open_time == datetime.fromtimestamp(
        1_700_000_000_000 / 1000,
        tz=UTC,
    )

    client.close()


def test_fetch_ticker_uses_futures_endpoints() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert request.url.params["symbol"] == "BTCUSDT"

        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(
                200,
                json={
                    "symbol": "BTCUSDT",
                    "bidPrice": "64210.00",
                    "askPrice": "64210.10",
                },
            )

        if request.url.path == "/fapi/v1/ticker/24hr":
            return httpx.Response(
                200,
                json={
                    "symbol": "BTCUSDT",
                    "lastPrice": "64210.05",
                    "quoteVolume": "985525363.36",
                },
            )

        raise AssertionError(f"unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    ticker = provider.fetch_ticker("BTC/USDT")

    assert requested_paths == [
        "/fapi/v1/ticker/bookTicker",
        "/fapi/v1/ticker/24hr",
    ]
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last_price == 64210.05
    assert ticker.bid_price == 64210.0
    assert ticker.ask_price == 64210.1
    assert ticker.source == "binance-futures"

    client.close()


def test_fetch_order_book_uses_futures_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fapi/v1/depth"
        assert request.url.params["symbol"] == "ETHUSDT"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "lastUpdateId": 1,
                "bids": [["2999.0", "2.0"]],
                "asks": [["3000.0", "1.5"]],
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    book = provider.fetch_order_book("ETH/USDT", depth=2)

    assert book.symbol == "ETH/USDT"
    assert book.best_bid.price == 2999.0
    assert book.best_ask.price == 3000.0
    assert book.source == "binance-futures"

    client.close()


def test_fetch_exchange_filters_supports_futures_notional_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fapi/v1/exchangeInfo"
        assert request.url.params["symbol"] == "BTCUSDT"
        return httpx.Response(
            200,
            json={
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "filters": [
                            {
                                "filterType": "PRICE_FILTER",
                                "tickSize": "0.10",
                            },
                            {
                                "filterType": "LOT_SIZE",
                                "stepSize": "0.001",
                                "minQty": "0.001",
                            },
                            {
                                "filterType": "MIN_NOTIONAL",
                                "notional": "5.0",
                            },
                        ],
                    }
                ]
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    filters = provider.fetch_exchange_filters("BTC/USDT")

    assert filters.symbol == "BTC/USDT"
    assert filters.tick_size == 0.1
    assert filters.step_size == 0.001
    assert filters.min_quantity == 0.001
    assert filters.min_notional == 5.0
    assert filters.source == "binance-futures"

    client.close()


def test_futures_provider_identity_and_default_base_url() -> None:
    provider = BinanceFuturesMarketDataProvider()

    assert provider.name == "binance-futures"
    assert provider.BASE_URL == "https://fapi.binance.com"

    provider.close()
