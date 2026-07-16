"""Tests for active futures symbol resolution."""

from pathlib import Path

from apex.application.futures_symbol_resolution import resolve_futures_symbols
from apex.domain.futures_market import FuturesContractMetadata


class StubUniverseProvider:
    name = "stub-futures"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_futures_contracts(self) -> tuple[FuturesContractMetadata, ...]:
        self.calls += 1
        return (
            _contract("ETHUSDT", "ETH"),
            _contract("BTCUSDT", "BTC"),
            _contract("BNBUSDT", "BNB", status="PENDING_TRADING"),
        )


def _contract(
    exchange_symbol: str,
    base_asset: str,
    *,
    status: str = "TRADING",
) -> FuturesContractMetadata:
    return FuturesContractMetadata(
        symbol=f"{base_asset}/USDT",
        exchange_symbol=exchange_symbol,
        base_asset=base_asset,
        quote_asset="USDT",
        status=status,
        contract_type="PERPETUAL",
        tick_size=0.01,
        step_size=0.001,
        minimum_quantity=0.001,
        minimum_notional=5.0,
    )


def test_resolves_live_exchange_universe_by_default() -> None:
    provider = StubUniverseProvider()

    symbols = resolve_futures_symbols(provider)

    assert symbols == ("BTC/USDT", "ETH/USDT")
    assert provider.calls == 1


def test_explicit_symbols_file_bypasses_live_discovery(tmp_path: Path) -> None:
    path = tmp_path / "symbols.yaml"
    path.write_text(
        "symbols:\n  - SOL/USDT\n  - BTC/USDT\n",
        encoding="utf-8",
    )
    provider = StubUniverseProvider()

    symbols = resolve_futures_symbols(provider, symbols_file=path)

    assert symbols == ("SOL/USDT", "BTC/USDT")
    assert provider.calls == 0


def test_live_resolution_applies_blacklist_and_allowlist() -> None:
    provider = StubUniverseProvider()

    symbols = resolve_futures_symbols(
        provider,
        blacklist=("ETHUSDT",),
        allowlist=("BTC/USDT", "ETH/USDT"),
    )

    assert symbols == ("BTC/USDT",)
