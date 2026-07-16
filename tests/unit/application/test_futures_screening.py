"""Tests for deterministic lightweight futures screening."""

from datetime import UTC, datetime

from apex.application.futures_screening import (
    screen_futures_universe,
)
from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import (
    FuturesScreenerConfig,
    FuturesScreeningExclusionReason,
    FuturesTickerSnapshot,
)


def _contract(
    exchange_symbol: str,
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


def _ticker(
    exchange_symbol: str,
    *,
    movement: float,
    volume: float,
    bid: float = 100.0,
    ask: float = 100.1,
) -> FuturesTickerSnapshot:
    return FuturesTickerSnapshot(
        symbol=exchange_symbol,
        exchange_symbol=exchange_symbol,
        last_price=(bid + ask) / 2,
        bid_price=bid,
        ask_price=ask,
        quote_volume_24h=volume,
        price_change_percentage_24h=movement,
        captured_at=datetime.now(UTC),
        source="test",
    )


def test_screen_futures_universe_filters_and_ranks() -> None:
    contracts = (
        _contract("AAAUSDT"),
        _contract("BBBUSDT"),
        _contract("CCCUSDT"),
        _contract("DDDUSDT"),
    )
    tickers = (
        _ticker(
            "AAAUSDT",
            movement=-8.0,
            volume=2_000_000.0,
        ),
        _ticker(
            "BBBUSDT",
            movement=8.0,
            volume=3_000_000.0,
        ),
        _ticker(
            "CCCUSDT",
            movement=2.0,
            volume=4_000_000.0,
        ),
        _ticker(
            "OUTUSDT",
            movement=20.0,
            volume=5_000_000.0,
        ),
    )

    result = screen_futures_universe(
        contracts,
        tickers,
        FuturesScreenerConfig(
            minimum_quote_volume_24h=1_000_000.0,
            maximum_spread_percentage=1.0,
            minimum_absolute_movement_percentage=3.0,
            shortlist_size=2,
        ),
    )

    assert [
        candidate.contract.exchange_symbol
        for candidate in result.candidates
    ] == [
        "BBBUSDT",
        "AAAUSDT",
    ]
    assert [
        candidate.rank for candidate in result.candidates
    ] == [1, 2]

    assert {
        (
            exclusion.exchange_symbol,
            exclusion.reason,
        )
        for exclusion in result.exclusions
    } == {
        (
            "CCCUSDT",
            FuturesScreeningExclusionReason
            .INSUFFICIENT_MOVEMENT,
        ),
        (
            "DDDUSDT",
            FuturesScreeningExclusionReason.MISSING_TICKER,
        ),
        (
            "OUTUSDT",
            FuturesScreeningExclusionReason.OUTSIDE_UNIVERSE,
        ),
    }

    assert result.total_contracts == 4
    assert result.total_tickers == 4
    assert result.shortlisted_count == 2


def test_screen_futures_universe_includes_threshold_boundaries() -> None:
    ticker = _ticker(
        "AAAUSDT",
        movement=-5.0,
        volume=1_000_000.0,
        bid=99.5,
        ask=100.5,
    )

    result = screen_futures_universe(
        (_contract("AAAUSDT"),),
        (ticker,),
        FuturesScreenerConfig(
            minimum_quote_volume_24h=1_000_000.0,
            maximum_spread_percentage=1.0,
            minimum_absolute_movement_percentage=5.0,
            shortlist_size=1,
        ),
    )

    assert result.shortlisted_count == 1
    assert result.exclusions == ()


def test_screen_futures_universe_excludes_low_liquidity() -> None:
    result = screen_futures_universe(
        (_contract("AAAUSDT"),),
        (
            _ticker(
                "AAAUSDT",
                movement=10.0,
                volume=999_999.0,
            ),
        ),
        FuturesScreenerConfig(
            minimum_quote_volume_24h=1_000_000.0,
            shortlist_size=1,
        ),
    )

    assert result.candidates == ()
    assert result.exclusions[0].reason == (
        FuturesScreeningExclusionReason.INSUFFICIENT_LIQUIDITY
    )


def test_screen_futures_universe_excludes_wide_spread() -> None:
    result = screen_futures_universe(
        (_contract("AAAUSDT"),),
        (
            _ticker(
                "AAAUSDT",
                movement=10.0,
                volume=2_000_000.0,
                bid=99.0,
                ask=101.0,
            ),
        ),
        FuturesScreenerConfig(
            maximum_spread_percentage=1.0,
            shortlist_size=1,
        ),
    )

    assert result.candidates == ()
    assert result.exclusions[0].reason == (
        FuturesScreeningExclusionReason.SPREAD_TOO_WIDE
    )


def test_screen_futures_universe_ranks_negative_and_positive_moves_equally() -> None:
    result = screen_futures_universe(
        (
            _contract("AAAUSDT"),
            _contract("BBBUSDT"),
        ),
        (
            _ticker(
                "AAAUSDT",
                movement=-12.0,
                volume=1_000_000.0,
            ),
            _ticker(
                "BBBUSDT",
                movement=10.0,
                volume=2_000_000.0,
            ),
        ),
        FuturesScreenerConfig(shortlist_size=2),
    )

    assert [
        candidate.contract.exchange_symbol
        for candidate in result.candidates
    ] == [
        "AAAUSDT",
        "BBBUSDT",
    ]


def test_screen_futures_universe_uses_volume_as_first_tiebreaker() -> None:
    result = screen_futures_universe(
        (
            _contract("AAAUSDT"),
            _contract("BBBUSDT"),
        ),
        (
            _ticker(
                "AAAUSDT",
                movement=10.0,
                volume=1_000_000.0,
            ),
            _ticker(
                "BBBUSDT",
                movement=-10.0,
                volume=2_000_000.0,
            ),
        ),
        FuturesScreenerConfig(shortlist_size=2),
    )

    assert [
        candidate.contract.exchange_symbol
        for candidate in result.candidates
    ] == [
        "BBBUSDT",
        "AAAUSDT",
    ]


def test_screen_futures_universe_uses_spread_then_symbol_for_ties() -> None:
    result = screen_futures_universe(
        (
            _contract("CCCUSDT"),
            _contract("AAAUSDT"),
            _contract("BBBUSDT"),
        ),
        (
            _ticker(
                "CCCUSDT",
                movement=10.0,
                volume=1_000_000.0,
                bid=99.9,
                ask=100.1,
            ),
            _ticker(
                "AAAUSDT",
                movement=10.0,
                volume=1_000_000.0,
                bid=99.95,
                ask=100.05,
            ),
            _ticker(
                "BBBUSDT",
                movement=10.0,
                volume=1_000_000.0,
                bid=99.95,
                ask=100.05,
            ),
        ),
        FuturesScreenerConfig(shortlist_size=3),
    )

    assert [
        candidate.contract.exchange_symbol
        for candidate in result.candidates
    ] == [
        "AAAUSDT",
        "BBBUSDT",
        "CCCUSDT",
    ]


def test_screen_futures_universe_normalizes_symbol_variants() -> None:
    contract = _contract("BTCUSDT")
    ticker = _ticker(
        "BTCUSDT",
        movement=5.0,
        volume=1_000_000.0,
    )

    variant_contract = FuturesContractMetadata(
        symbol=contract.symbol,
        exchange_symbol="btc-usdt",
        base_asset=contract.base_asset,
        quote_asset=contract.quote_asset,
        status=contract.status,
        contract_type=contract.contract_type,
        tick_size=contract.tick_size,
        step_size=contract.step_size,
        minimum_quantity=contract.minimum_quantity,
        minimum_notional=contract.minimum_notional,
    )

    result = screen_futures_universe(
        (variant_contract,),
        (ticker,),
        FuturesScreenerConfig(shortlist_size=1),
    )

    assert result.shortlisted_count == 1
    assert result.exclusions == ()


def test_screen_futures_universe_does_not_mutate_inputs() -> None:
    contracts = [
        _contract("AAAUSDT"),
        _contract("BBBUSDT"),
    ]
    tickers = [
        _ticker(
            "AAAUSDT",
            movement=5.0,
            volume=1_000_000.0,
        ),
        _ticker(
            "BBBUSDT",
            movement=6.0,
            volume=2_000_000.0,
        ),
    ]

    original_contracts = list(contracts)
    original_tickers = list(tickers)

    screen_futures_universe(
        contracts,
        tickers,
        FuturesScreenerConfig(shortlist_size=1),
    )

    assert contracts == original_contracts
    assert tickers == original_tickers
