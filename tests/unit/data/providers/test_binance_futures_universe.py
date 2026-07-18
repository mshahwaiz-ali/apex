"""Tests for Binance futures universe metadata."""

import httpx
import pytest

from apex.data.providers.binance_futures_universe import (
    BinanceFuturesUniverseProvider,
)
from apex.data.providers.errors import ProviderResponseError


def _symbol(
    symbol: str,
    base_asset: str,
    *,
    quote_asset: str = "USDT",
    status: str = "TRADING",
    contract_type: str = "PERPETUAL",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "baseAsset": base_asset,
        "quoteAsset": quote_asset,
        "status": status,
        "contractType": contract_type,
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "tickSize": "0.01",
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


def test_fetch_futures_contracts_normalizes_and_sorts_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fapi/v1/exchangeInfo"
        return httpx.Response(
            200,
            json={
                "symbols": [
                    _symbol("ETHUSDT", "ETH"),
                    _symbol("BTCUSDT", "BTC"),
                ]
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(client=client)

    contracts = provider.fetch_futures_contracts()

    assert tuple(item.exchange_symbol for item in contracts) == (
        "BTCUSDT",
        "ETHUSDT",
    )

    bitcoin = contracts[0]
    assert bitcoin.symbol == "BTC/USDT"
    assert bitcoin.base_asset == "BTC"
    assert bitcoin.quote_asset == "USDT"
    assert bitcoin.status == "TRADING"
    assert bitcoin.contract_type == "PERPETUAL"
    assert bitcoin.tick_size == 0.01
    assert bitcoin.step_size == 0.001
    assert bitcoin.minimum_quantity == 0.001
    assert bitcoin.minimum_notional == 5.0

    client.close()


def test_fetch_futures_contracts_reuses_cache_until_expiry() -> None:
    now = [10.0]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.path == "/fapi/v1/exchangeInfo"
        calls += 1
        return httpx.Response(
            200,
            json={"symbols": [_symbol("BTCUSDT", "BTC")]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(
        client=client,
        metadata_cache_ttl_seconds=60.0,
        monotonic=lambda: now[0],
    )

    first = provider.fetch_futures_contracts()
    now[0] = 69.0
    second = provider.fetch_futures_contracts()
    now[0] = 70.0
    third = provider.fetch_futures_contracts()

    assert first is second
    assert third == first
    assert calls == 2

    client.close()


def test_clear_metadata_cache_forces_refresh() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        symbol = "BTCUSDT" if calls == 1 else "ETHUSDT"
        base_asset = "BTC" if calls == 1 else "ETH"
        return httpx.Response(
            200,
            json={"symbols": [_symbol(symbol, base_asset)]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(
        client=client,
        metadata_cache_ttl_seconds=3_600.0,
        monotonic=lambda: 100.0,
    )

    assert provider.fetch_futures_contracts()[0].exchange_symbol == "BTCUSDT"
    provider.clear_metadata_cache()
    assert provider.fetch_futures_contracts()[0].exchange_symbol == "ETHUSDT"
    assert calls == 2

    client.close()


def test_fetch_futures_contracts_skips_malformed_rows() -> None:
    invalid = _symbol("BROKENUSDT", "BROKEN")
    invalid["filters"] = []

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "symbols": [
                        invalid,
                        _symbol("BTCUSDT", "BTC"),
                        {"symbol": ""},
                    ]
                },
            )
        ),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(client=client)

    contracts = provider.fetch_futures_contracts()

    assert tuple(item.exchange_symbol for item in contracts) == ("BTCUSDT",)

    client.close()


@pytest.mark.parametrize(
    "payload",
    (
        [],
        {},
        {"symbols": "invalid"},
    ),
)
def test_fetch_futures_contracts_rejects_invalid_top_level_payload(
    payload: object,
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(client=client)

    with pytest.raises(ProviderResponseError):
        provider.fetch_futures_contracts()

    client.close()


def test_fetch_futures_contracts_rejects_when_all_contract_rows_are_invalid() -> None:
    invalid = _symbol("BTCUSDT", "BTC")
    invalid["filters"] = []

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"symbols": [invalid, None, {"symbol": ""}]},
            )
        ),
        base_url="https://fapi.binance.com",
    )
    provider = BinanceFuturesUniverseProvider(client=client)

    with pytest.raises(
        ProviderResponseError,
        match="contained no valid contracts",
    ):
        provider.fetch_futures_contracts()

    client.close()


def test_rejects_negative_metadata_cache_ttl() -> None:
    with pytest.raises(ValueError, match="TTL cannot be negative"):
        BinanceFuturesUniverseProvider(metadata_cache_ttl_seconds=-1.0)
