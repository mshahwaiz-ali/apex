"""Tests for deterministic futures-universe filtering."""

from apex.application.futures_universe import (
    filter_futures_universe,
    futures_universe_symbols,
)
from apex.domain.futures_market import FuturesContractMetadata


def _contract(
    symbol: str,
    *,
    quote_asset: str = "USDT",
    status: str = "TRADING",
    contract_type: str = "PERPETUAL",
) -> FuturesContractMetadata:
    base_asset = symbol.removesuffix(quote_asset)
    return FuturesContractMetadata(
        symbol=f"{base_asset}/{quote_asset}",
        exchange_symbol=symbol,
        base_asset=base_asset,
        quote_asset=quote_asset,
        status=status,
        contract_type=contract_type,
        tick_size=0.01,
        step_size=0.001,
        minimum_quantity=0.001,
        minimum_notional=5.0,
    )


def test_filters_active_usdt_perpetual_contracts_deterministically() -> None:
    contracts = (
        _contract("ETHUSDT"),
        _contract("BTCUSDT"),
        _contract("BNBUSDT", status="PENDING_TRADING"),
        _contract("BTCUSDC", quote_asset="USDC"),
        _contract("ETHUSDT_250627", contract_type="CURRENT_QUARTER"),
    )

    selected = filter_futures_universe(contracts)

    assert tuple(item.exchange_symbol for item in selected) == (
        "BTCUSDT",
        "ETHUSDT",
    )
    assert futures_universe_symbols(contracts) == (
        "BTC/USDT",
        "ETH/USDT",
    )


def test_blacklist_and_allowlist_use_normalized_symbol_forms() -> None:
    contracts = (
        _contract("BTCUSDT"),
        _contract("ETHUSDT"),
        _contract("SOLUSDT"),
    )

    selected = filter_futures_universe(
        contracts,
        blacklist=("eth/usdt",),
        allowlist=("BTC-USDT", "ETHUSDT"),
    )

    assert tuple(item.exchange_symbol for item in selected) == ("BTCUSDT",)


def test_duplicate_exchange_symbols_use_deterministic_tie_break() -> None:
    canonical = _contract("BTCUSDT")
    alias = FuturesContractMetadata(
        symbol="XBT/USDT",
        exchange_symbol="BTCUSDT",
        base_asset="XBT",
        quote_asset="USDT",
        status="TRADING",
        contract_type="PERPETUAL",
        tick_size=0.01,
        step_size=0.001,
        minimum_quantity=0.001,
        minimum_notional=5.0,
    )

    forward = filter_futures_universe((alias, canonical))
    reverse = filter_futures_universe((canonical, alias))

    assert forward == (canonical,)
    assert reverse == forward
