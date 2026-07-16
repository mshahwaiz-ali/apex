"""Deterministic lightweight futures-universe screening."""

from __future__ import annotations

from collections.abc import Iterable

from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import (
    FuturesScreenerConfig,
    FuturesScreeningCandidate,
    FuturesScreeningExclusion,
    FuturesScreeningExclusionReason,
    FuturesScreeningResult,
    FuturesTickerSnapshot,
)


def screen_futures_universe(
    contracts: Iterable[FuturesContractMetadata],
    tickers: Iterable[FuturesTickerSnapshot],
    config: FuturesScreenerConfig,
) -> FuturesScreeningResult:
    """Filter and rank futures tickers without fetching candle data."""

    contracts_by_symbol = {
        _normalize_symbol(contract.exchange_symbol): contract
        for contract in contracts
    }
    tickers_by_symbol = {
        _normalize_symbol(ticker.exchange_symbol): ticker
        for ticker in tickers
    }

    exclusions: list[FuturesScreeningExclusion] = []
    eligible: list[
        tuple[FuturesContractMetadata, FuturesTickerSnapshot]
    ] = []

    outside_universe = (
        tickers_by_symbol.keys() - contracts_by_symbol.keys()
    )
    for exchange_symbol in sorted(outside_universe):
        exclusions.append(
            FuturesScreeningExclusion(
                exchange_symbol=exchange_symbol,
                reason=(
                    FuturesScreeningExclusionReason.OUTSIDE_UNIVERSE
                ),
                detail=(
                    "Ticker is not part of the selected futures "
                    "contract universe."
                ),
            )
        )

    for exchange_symbol in sorted(contracts_by_symbol):
        contract = contracts_by_symbol[exchange_symbol]
        ticker = tickers_by_symbol.get(exchange_symbol)

        if ticker is None:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(
                        FuturesScreeningExclusionReason.MISSING_TICKER
                    ),
                    detail=(
                        "No valid batch ticker was available for "
                        "this contract."
                    ),
                )
            )
            continue

        if (
            ticker.quote_volume_24h
            < config.minimum_quote_volume_24h
        ):
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(
                        FuturesScreeningExclusionReason
                        .INSUFFICIENT_LIQUIDITY
                    ),
                    detail=(
                        f"24h quote volume "
                        f"{ticker.quote_volume_24h} is below "
                        f"{config.minimum_quote_volume_24h}."
                    ),
                )
            )
            continue

        if (
            ticker.spread_percentage
            > config.maximum_spread_percentage
        ):
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(
                        FuturesScreeningExclusionReason
                        .SPREAD_TOO_WIDE
                    ),
                    detail=(
                        f"Spread {ticker.spread_percentage} is "
                        f"above "
                        f"{config.maximum_spread_percentage} "
                        f"percent."
                    ),
                )
            )
            continue

        if (
            ticker.absolute_movement_percentage
            < config.minimum_absolute_movement_percentage
        ):
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(
                        FuturesScreeningExclusionReason
                        .INSUFFICIENT_MOVEMENT
                    ),
                    detail=(
                        f"Absolute 24h movement "
                        f"{ticker.absolute_movement_percentage} "
                        f"is below "
                        f"{config.minimum_absolute_movement_percentage} "
                        f"percent."
                    ),
                )
            )
            continue

        eligible.append((contract, ticker))

    ranked = sorted(
        eligible,
        key=lambda item: (
            -item[1].absolute_movement_percentage,
            -item[1].quote_volume_24h,
            item[1].spread_percentage,
            _normalize_symbol(item[0].exchange_symbol),
        ),
    )[: config.shortlist_size]

    candidates = tuple(
        FuturesScreeningCandidate(
            rank=rank,
            contract=contract,
            ticker=ticker,
        )
        for rank, (contract, ticker) in enumerate(
            ranked,
            start=1,
        )
    )

    return FuturesScreeningResult(
        total_contracts=len(contracts_by_symbol),
        total_tickers=len(tickers_by_symbol),
        candidates=candidates,
        exclusions=tuple(exclusions),
    )


def _normalize_symbol(value: str) -> str:
    normalized = (
        value.strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
    )

    if not normalized:
        raise ValueError("symbol cannot be empty")

    return normalized
