from datetime import UTC, datetime

import httpx
import pytest

from apex.data.providers.binance import BinanceMarketDataProvider
from apex.data.providers.errors import ProviderRequestError, ProviderResponseError
from apex.data.providers.http import RetryPolicy


def test_fetch_candles_normalizes_binance_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "15m"
        assert request.url.params["limit"] == "2"

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
                    1_700_000_899_999,
                ],
                [
                    1_700_000_900_000,
                    "105.0",
                    "112.0",
                    "101.0",
                    "108.0",
                    "67.89",
                    4_100_000_000_000,
                ],
            ],
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    )

    provider = BinanceMarketDataProvider(client=client)
    candles = provider.fetch_candles("BTC/USDT", "15m", limit=2)

    assert len(candles) == 2

    first = candles[0]
    assert first.symbol == "BTC/USDT"
    assert first.timeframe == "15m"
    assert first.open == 100.0
    assert first.high == 110.0
    assert first.low == 95.0
    assert first.close == 105.0
    assert first.volume == 123.45
    assert first.source == "binance"
    assert first.is_closed is True
    assert first.open_time == datetime.fromtimestamp(
        1_700_000_000_000 / 1000,
        tz=UTC,
    )

    assert candles[1].is_closed is False

    client.close()


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("BTC/USDT", "BTCUSDT"),
        ("eth-usdt", "ETHUSDT"),
        (" SOLUSDT ", "SOLUSDT"),
    ],
)
def test_normalize_symbol(symbol: str, expected: str) -> None:
    assert BinanceMarketDataProvider._normalize_symbol(symbol) == expected


def test_rejects_unsupported_timeframe() -> None:
    provider = BinanceMarketDataProvider(
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
            base_url="https://api.binance.com",
        )
    )

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        provider.fetch_candles("BTC/USDT", "2m")


@pytest.mark.parametrize("limit", [0, 1001])
def test_rejects_invalid_limit(limit: int) -> None:
    provider = BinanceMarketDataProvider(
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
            base_url="https://api.binance.com",
        )
    )

    with pytest.raises(ValueError, match="limit must be between 1 and 1000"):
        provider.fetch_candles("BTC/USDT", "15m", limit=limit)


def test_fetch_ticker_normalizes_binance_responses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/ticker/bookTicker":
            assert request.url.params["symbol"] == "BTCUSDT"
            return httpx.Response(
                200,
                json={
                    "symbol": "BTCUSDT",
                    "bidPrice": "64210.00",
                    "askPrice": "64210.01",
                },
            )

        if request.url.path == "/api/v3/ticker/24hr":
            assert request.url.params["symbol"] == "BTCUSDT"
            return httpx.Response(
                200,
                json={
                    "symbol": "BTCUSDT",
                    "lastPrice": "64210.01",
                    "quoteVolume": "985525363.364469",
                },
            )

        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    )

    provider = BinanceMarketDataProvider(client=client)
    ticker = provider.fetch_ticker("BTC/USDT")

    assert ticker.symbol == "BTC/USDT"
    assert ticker.last_price == 64210.01
    assert ticker.bid_price == 64210.0
    assert ticker.ask_price == 64210.01
    assert ticker.quote_volume_24h == 985525363.364469
    assert ticker.source == "binance"
    assert ticker.spread == pytest.approx(0.01)

    client.close()


@pytest.mark.parametrize(
    ("path", "payload", "expected_message"),
    [
        (
            "/api/v3/ticker/bookTicker",
            [],
            "Binance book ticker response must be an object",
        ),
        (
            "/api/v3/ticker/24hr",
            [],
            "Binance 24h ticker response must be an object",
        ),
    ],
)
def test_fetch_ticker_rejects_invalid_payload(
    path: str,
    payload: object,
    expected_message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return httpx.Response(200, json=payload)

        if request.url.path == "/api/v3/ticker/bookTicker":
            return httpx.Response(
                200,
                json={"bidPrice": "100", "askPrice": "101"},
            )

        return httpx.Response(
            200,
            json={"lastPrice": "100.5", "quoteVolume": "1000000"},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    )

    provider = BinanceMarketDataProvider(client=client)

    with pytest.raises(ProviderResponseError, match=expected_message):
        provider.fetch_ticker("BTC/USDT")

    client.close()


def test_fetch_candles_retries_retryable_binance_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(503, request=request)

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
                    1_700_000_899_999,
                ]
            ],
            request=request,
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    )
    provider = BinanceMarketDataProvider(
        client=client,
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay_seconds=0,
        ),
        sleep=lambda _: None,
    )

    candles = provider.fetch_candles("BTC/USDT", "15m", limit=1)

    assert len(candles) == 1
    assert attempts == 2

    client.close()


def test_fetch_candles_normalizes_non_retryable_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, request=request)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    )
    provider = BinanceMarketDataProvider(
        client=client,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.fetch_candles("INVALID/USDT", "15m", limit=1)

    error = exc_info.value
    assert error.provider == "binance"
    assert error.operation == "fetch candles"
    assert error.status_code == 400
    assert error.retryable is False

    client.close()


def test_fetch_ticker_normalizes_missing_required_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/ticker/bookTicker":
            return httpx.Response(
                200,
                json={
                    "bidPrice": "100",
                    "askPrice": "101",
                },
                request=request,
            )

        return httpx.Response(
            200,
            json={
                "quoteVolume": "1000000",
            },
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    ) as client:
        provider = BinanceMarketDataProvider(client=client)

        with pytest.raises(
            ProviderResponseError,
            match="Invalid Binance ticker response fields",
        ) as exc_info:
            provider.fetch_ticker("BTC/USDT")

    error = exc_info.value
    assert error.provider == "binance"
    assert error.operation == "parse ticker"
    assert isinstance(error.__cause__, KeyError)


def test_fetch_ticker_normalizes_non_numeric_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/ticker/bookTicker":
            return httpx.Response(
                200,
                json={
                    "bidPrice": "not-a-number",
                    "askPrice": "101",
                },
                request=request,
            )

        return httpx.Response(
            200,
            json={
                "lastPrice": "100.5",
                "quoteVolume": "1000000",
            },
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    ) as client:
        provider = BinanceMarketDataProvider(client=client)

        with pytest.raises(
            ProviderResponseError,
            match="Invalid Binance ticker response fields",
        ) as exc_info:
            provider.fetch_ticker("BTC/USDT")

    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "not-a-number",
        None,
    ],
)
def test_fetch_candles_normalizes_invalid_numeric_values(
    invalid_value: object,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                [
                    1_700_000_000_000,
                    invalid_value,
                    "110.0",
                    "95.0",
                    "105.0",
                    "123.45",
                    1_700_000_899_999,
                ]
            ],
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    ) as client:
        provider = BinanceMarketDataProvider(client=client)

        with pytest.raises(
            ProviderResponseError,
            match="Invalid Binance candle values",
        ) as exc_info:
            provider.fetch_candles("BTC/USDT", "15m", limit=1)

    error = exc_info.value
    assert error.provider == "binance"
    assert error.operation == "parse candles"


def test_fetch_candles_normalizes_invalid_ohlc_relationship() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                [
                    1_700_000_000_000,
                    "100.0",
                    "90.0",
                    "95.0",
                    "105.0",
                    "123.45",
                    1_700_000_899_999,
                ]
            ],
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    ) as client:
        provider = BinanceMarketDataProvider(client=client)

        with pytest.raises(
            ProviderResponseError,
            match="Invalid Binance candle values",
        ):
            provider.fetch_candles("BTC/USDT", "15m", limit=1)


def test_fetch_candles_normalizes_out_of_range_timestamp() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                [
                    10**100,
                    "100.0",
                    "110.0",
                    "95.0",
                    "105.0",
                    "123.45",
                    10**100,
                ]
            ],
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.binance.com",
    ) as client:
        provider = BinanceMarketDataProvider(client=client)

        with pytest.raises(
            ProviderResponseError,
            match="Invalid Binance timestamp",
        ) as exc_info:
            provider.fetch_candles("BTC/USDT", "15m", limit=1)

    assert exc_info.value.operation == "parse candles"
