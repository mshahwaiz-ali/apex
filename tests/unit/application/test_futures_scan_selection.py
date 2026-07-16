"""Tests for futures scan symbol selection."""

from datetime import UTC, datetime
from pathlib import Path

from apex.application.futures_scan_selection import (
    select_futures_scan_symbols,
    serialize_futures_screening,
)
from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import (
    FuturesScreenerConfig,
    FuturesTickerSnapshot,
)


def _contract(
    exchange_symbol: str,
    *,
    status: str = "TRADING",
) -> FuturesContractMetadata:
    base_asset = exchange_symbol.removesuffix("USDT")

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


def _ticker(
    exchange_symbol: str,
    *,
    movement: float,
    volume: float,
) -> FuturesTickerSnapshot:
    return FuturesTickerSnapshot(
        symbol=exchange_symbol,
        exchange_symbol=exchange_symbol,
        last_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        quote_volume_24h=volume,
        price_change_percentage_24h=movement,
        captured_at=datetime.now(UTC),
        source="test",
    )


class StubUniverseProvider:
    name = "stub-universe"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_futures_contracts(
        self,
    ) -> tuple[FuturesContractMetadata, ...]:
        self.calls += 1
        return (
            _contract("AAAUSDT"),
            _contract("BBBUSDT"),
            _contract(
                "PENDINGUSDT",
                status="PENDING_TRADING",
            ),
        )


class StubScreenerProvider:
    name = "stub-screener"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_futures_tickers(
        self,
    ) -> tuple[FuturesTickerSnapshot, ...]:
        self.calls += 1
        return (
            _ticker(
                "AAAUSDT",
                movement=4.0,
                volume=2_000_000.0,
            ),
            _ticker(
                "BBBUSDT",
                movement=-8.0,
                volume=3_000_000.0,
            ),
            _ticker(
                "OUTUSDT",
                movement=20.0,
                volume=5_000_000.0,
            ),
        )


def test_static_override_bypasses_all_live_screening(
    tmp_path: Path,
) -> None:
    symbols_file = tmp_path / "symbols.yaml"
    symbols_file.write_text(
        "symbols:\n  - SOL/USDT\n  - BTC/USDT\n",
        encoding="utf-8",
    )
    universe = StubUniverseProvider()
    screener = StubScreenerProvider()

    selection = select_futures_scan_symbols(
        universe,
        screener,
        config=FuturesScreenerConfig(),
        symbols_file=symbols_file,
    )

    assert selection.symbols == (
        "SOL/USDT",
        "BTC/USDT",
    )
    assert selection.screening is None
    assert selection.used_static_override is True
    assert universe.calls == 0
    assert screener.calls == 0


def test_dynamic_selection_screens_and_ranks_contracts() -> None:
    universe = StubUniverseProvider()
    screener = StubScreenerProvider()

    selection = select_futures_scan_symbols(
        universe,
        screener,
        config=FuturesScreenerConfig(
            minimum_quote_volume_24h=1_000_000.0,
            maximum_spread_percentage=1.0,
            minimum_absolute_movement_percentage=3.0,
            shortlist_size=1,
        ),
    )

    assert selection.symbols == ("BBB/USDT",)
    assert selection.screening is not None
    assert selection.used_static_override is False
    assert universe.calls == 1
    assert screener.calls == 1
    assert selection.screening.total_contracts == 2
    assert selection.screening.total_tickers == 3
    assert selection.screening.shortlisted_count == 1


def test_dynamic_selection_serializes_screening_diagnostics() -> None:
    selection = select_futures_scan_symbols(
        StubUniverseProvider(),
        StubScreenerProvider(),
        config=FuturesScreenerConfig(
            minimum_quote_volume_24h=1_000_000.0,
            maximum_spread_percentage=1.0,
            minimum_absolute_movement_percentage=3.0,
            shortlist_size=2,
        ),
    )

    assert selection.screening is not None

    payload = serialize_futures_screening(
        selection.screening
    )

    assert payload["total_contracts"] == 2
    assert payload["total_tickers"] == 3
    assert payload["shortlisted_count"] == 2

    candidates = payload["candidates"]

    assert isinstance(candidates, list)
    assert candidates[0]["symbol"] == "BBB/USDT"
    assert candidates[0]["rank"] == 1

    exclusions = payload["exclusions"]

    assert isinstance(exclusions, list)
    assert exclusions[0]["exchange_symbol"] == "OUTUSDT"
    assert exclusions[0]["reason"] == "outside_universe"
