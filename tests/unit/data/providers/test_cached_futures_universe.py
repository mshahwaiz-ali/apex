from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.data.providers.cached_futures_universe import (
    CachedFuturesUniverseProvider,
)
from apex.domain.futures_market import FuturesContractMetadata

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _contract(
    exchange_symbol: str = "BTCUSDT",
) -> FuturesContractMetadata:
    base_asset = exchange_symbol.removesuffix("USDT")
    return FuturesContractMetadata(
        symbol=f"{base_asset}/USDT",
        exchange_symbol=exchange_symbol,
        base_asset=base_asset,
        quote_asset="USDT",
        status="TRADING",
        contract_type="PERPETUAL",
        tick_size=0.01,
        step_size=0.001,
        minimum_quantity=0.001,
        minimum_notional=5.0,
    )


class StubUniverseProvider:
    name = "stub-futures"

    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    def fetch_futures_contracts(
        self,
    ) -> tuple[FuturesContractMetadata, ...]:
        self.calls += 1
        return (_contract(),)

    def close(self) -> None:
        self.closed = True


def test_fresh_metadata_cache_avoids_second_provider_request(
    tmp_path: Path,
) -> None:
    provider = StubUniverseProvider()
    cached = CachedFuturesUniverseProvider(
        provider,
        tmp_path / "contracts.json",
        time_to_live=timedelta(hours=1),
        now=lambda: NOW,
    )

    first = cached.fetch_futures_contracts()
    second = cached.fetch_futures_contracts()

    assert first == second
    assert provider.calls == 1


def test_cache_is_reused_by_new_provider_instance(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "contracts.json"
    first_provider = StubUniverseProvider()
    first = CachedFuturesUniverseProvider(
        first_provider,
        cache_path,
        time_to_live=timedelta(hours=1),
        now=lambda: NOW,
    )
    first.fetch_futures_contracts()

    second_provider = StubUniverseProvider()
    second = CachedFuturesUniverseProvider(
        second_provider,
        cache_path,
        time_to_live=timedelta(hours=1),
        now=lambda: NOW + timedelta(minutes=10),
    )

    contracts = second.fetch_futures_contracts()

    assert contracts == (_contract(),)
    assert first_provider.calls == 1
    assert second_provider.calls == 0


def test_stale_cache_refreshes_live_metadata(
    tmp_path: Path,
) -> None:
    current_time = NOW
    provider = StubUniverseProvider()
    cached = CachedFuturesUniverseProvider(
        provider,
        tmp_path / "contracts.json",
        time_to_live=timedelta(minutes=30),
        now=lambda: current_time,
    )

    cached.fetch_futures_contracts()
    current_time = NOW + timedelta(minutes=31)
    cached.fetch_futures_contracts()

    assert provider.calls == 2


def test_corrupt_cache_falls_back_to_live_provider(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "contracts.json"
    cache_path.write_text("{not-json", encoding="utf-8")
    provider = StubUniverseProvider()
    cached = CachedFuturesUniverseProvider(
        provider,
        cache_path,
        time_to_live=timedelta(hours=1),
        now=lambda: NOW,
    )

    contracts = cached.fetch_futures_contracts()

    assert contracts == (_contract(),)
    assert provider.calls == 1


def test_close_is_delegated_to_wrapped_provider(
    tmp_path: Path,
) -> None:
    provider = StubUniverseProvider()
    cached = CachedFuturesUniverseProvider(
        provider,
        tmp_path / "contracts.json",
        time_to_live=timedelta(hours=1),
        now=lambda: NOW,
    )

    cached.close()

    assert provider.closed is True
