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


def test_enriched_kline_fields_are_preserved() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                [
                    1_700_000_000_000,
                    "100",
                    "110",
                    "95",
                    "105",
                    "12",
                    1_700_000_299_999,
                    "1250",
                    42,
                    "7",
                    "730",
                    "0",
                ]
            ],
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://fapi.binance.com"
    ) as client:
        candle = BinanceFuturesMarketDataProvider(client=client).fetch_candles(
            "BTCUSDT", "5m", limit=1
        )[0]

    assert candle.quote_volume == 1250
    assert candle.trade_count == 42
    assert candle.taker_buy_base_volume == 7
    assert candle.taker_buy_quote_volume == 730


def test_fetch_premium_index_keeps_mark_index_and_funding_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fapi/v1/premiumIndex"
        return httpx.Response(
            200,
            json={
                "symbol": "BTCUSDT",
                "markPrice": "101",
                "indexPrice": "100",
                "lastFundingRate": "0.0001",
                "nextFundingTime": 1_800_000_000_000,
                "time": 1_700_000_000_000,
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://fapi.binance.com"
    ) as client:
        snapshot = BinanceFuturesMarketDataProvider(client=client).fetch_premium_index("BTCUSDT")

    assert snapshot.mark_price == 101
    assert snapshot.index_price == 100
    assert snapshot.basis_percentage == 1


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
                        "status": "TRADING",
                        "onboardDate": 1609459200000,
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
    assert filters.contract_status == "TRADING"
    assert filters.onboarded_at == datetime(2021, 1, 1, tzinfo=UTC)

    client.close()


def test_futures_provider_identity_and_default_base_url() -> None:
    provider = BinanceFuturesMarketDataProvider()

    assert provider.name == "binance-futures"
    assert provider.BASE_URL == "https://fapi.binance.com"

    provider.close()


def test_fetch_optional_futures_evidence_normalizes_chronological_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["limit"] == "2"
        if request.url.path == "/fapi/v1/fundingRate":
            return httpx.Response(
                200,
                json=[
                    {"fundingRate": "0.0002", "fundingTime": 1_700_000_600_000},
                    {"fundingRate": "0.0001", "fundingTime": 1_700_000_000_000},
                ],
            )
        assert request.url.params["period"] == "5m"
        if request.url.path == "/futures/data/openInterestHist":
            return httpx.Response(
                200,
                json=[
                    {
                        "sumOpenInterest": "1200",
                        "sumOpenInterestValue": "240000",
                        "timestamp": 1_700_000_000_000,
                    }
                ],
            )
        if request.url.path == "/futures/data/takerlongshortRatio":
            return httpx.Response(
                200,
                json=[
                    {
                        "buyVol": "600",
                        "sellVol": "400",
                        "buySellRatio": "1.5",
                        "timestamp": 1_700_000_000_000,
                    }
                ],
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    funding = provider.fetch_funding_rates("BTC/USDT", limit=2)
    open_interest = provider.fetch_open_interest_history("BTC/USDT", limit=2)
    taker = provider.fetch_taker_flow_history("BTC/USDT", limit=2)

    assert [item.funding_rate for item in funding] == [0.0001, 0.0002]
    assert open_interest[0].open_interest_value == 240_000
    assert taker[0].buy_sell_ratio == 1.5
    client.close()


def test_fetch_futures_tickers_uses_two_batch_endpoints() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert "symbol" not in request.url.params

        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "ETHUSDT",
                        "bidPrice": "2999.0",
                        "askPrice": "3000.0",
                    },
                    {
                        "symbol": "BTCUSDT",
                        "bidPrice": "64210.0",
                        "askPrice": "64210.1",
                    },
                ],
            )

        if request.url.path == "/fapi/v1/ticker/24hr":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "64210.05",
                        "quoteVolume": "985525363.36",
                        "priceChangePercent": "4.5",
                        "highPrice": "65000.0",
                        "lowPrice": "61000.0",
                        "count": 12345,
                    },
                    {
                        "symbol": "ETHUSDT",
                        "lastPrice": "2999.5",
                        "quoteVolume": "500000000.0",
                        "priceChangePercent": "-6.0",
                    },
                ],
            )

        raise AssertionError(f"unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    tickers = provider.fetch_futures_tickers()

    assert requested_paths == [
        "/fapi/v1/ticker/bookTicker",
        "/fapi/v1/ticker/24hr",
    ]
    assert [ticker.exchange_symbol for ticker in tickers] == [
        "BTCUSDT",
        "ETHUSDT",
    ]

    assert tickers[0].last_price == 64210.05
    assert tickers[0].bid_price == 64210.0
    assert tickers[0].ask_price == 64210.1
    assert tickers[0].high_price_24h == 65000.0
    assert tickers[0].low_price_24h == 61000.0
    assert tickers[0].trade_count_24h == 12345
    assert tickers[0].source == "binance-futures"

    assert tickers[1].high_price_24h is None
    assert tickers[1].low_price_24h is None
    assert tickers[1].trade_count_24h is None

    client.close()


def test_fetch_futures_tickers_skips_invalid_and_unmatched_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "bidPrice": "64210.0",
                        "askPrice": "64210.1",
                    },
                    {
                        "symbol": "BROKENUSDT",
                        "bidPrice": "bad",
                        "askPrice": "1.0",
                    },
                    {
                        "symbol": "BOOKONLYUSDT",
                        "bidPrice": "1.0",
                        "askPrice": "1.1",
                    },
                ],
            )

        if request.url.path == "/fapi/v1/ticker/24hr":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "64210.05",
                        "quoteVolume": "985525363.36",
                        "priceChangePercent": "4.5",
                    },
                    {
                        "symbol": "STATSINVALIDUSDT",
                        "lastPrice": "bad",
                        "quoteVolume": "1000.0",
                        "priceChangePercent": "1.0",
                    },
                    {
                        "symbol": "STATSONLYUSDT",
                        "lastPrice": "1.0",
                        "quoteVolume": "1000.0",
                        "priceChangePercent": "1.0",
                    },
                ],
            )

        raise AssertionError(f"unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    tickers = provider.fetch_futures_tickers()

    assert [ticker.exchange_symbol for ticker in tickers] == ["BTCUSDT"]

    client.close()


def test_fetch_futures_tickers_skips_invalid_joined_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "bidPrice": "101.0",
                        "askPrice": "100.0",
                    }
                ],
            )

        if request.url.path == "/fapi/v1/ticker/24hr":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "100.0",
                        "quoteVolume": "1000.0",
                        "priceChangePercent": "1.0",
                    }
                ],
            )

        raise AssertionError(f"unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    assert provider.fetch_futures_tickers() == ()

    client.close()


def test_fetch_futures_tickers_rejects_invalid_book_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(
                200,
                json={"symbol": "BTCUSDT"},
            )

        return httpx.Response(200, json=[])

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    import pytest

    from apex.data.providers.errors import ProviderResponseError

    with pytest.raises(
        ProviderResponseError,
        match="book ticker response must be a list",
    ):
        provider.fetch_futures_tickers()

    client.close()


def test_fetch_futures_tickers_rejects_invalid_24h_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fapi/v1/ticker/bookTicker":
            return httpx.Response(200, json=[])

        return httpx.Response(
            200,
            json={"symbol": "BTCUSDT"},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesMarketDataProvider(client=client)

    import pytest

    from apex.data.providers.errors import ProviderResponseError

    with pytest.raises(
        ProviderResponseError,
        match="24h ticker response must be a list",
    ):
        provider.fetch_futures_tickers()

    client.close()
