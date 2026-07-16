"""Resolve symbols for one futures scan execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apex.application.analysis import load_symbols
from apex.application.futures_screening import (
    screen_futures_universe,
)
from apex.application.futures_universe import (
    filter_futures_universe,
)
from apex.data.providers.base import (
    FuturesMarketScreenerProvider,
    FuturesUniverseProvider,
)
from apex.domain.futures_screening import (
    FuturesScreenerConfig,
    FuturesScreeningResult,
)


@dataclass(frozen=True, slots=True)
class FuturesScanSelection:
    """Resolved symbols and optional dynamic-screening diagnostics."""

    symbols: tuple[str, ...]
    screening: FuturesScreeningResult | None

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("futures scan selection cannot be empty")

    @property
    def used_static_override(self) -> bool:
        """Return whether screening was bypassed by a symbol file."""

        return self.screening is None


def select_futures_scan_symbols(
    universe_provider: FuturesUniverseProvider,
    screener_provider: FuturesMarketScreenerProvider,
    *,
    config: FuturesScreenerConfig,
    symbols_file: Path | None = None,
    quote_asset: str = "USDT",
    blacklist: tuple[str, ...] = (),
    allowlist: tuple[str, ...] | None = None,
) -> FuturesScanSelection:
    """Resolve a static override or dynamically screen live contracts."""

    if symbols_file is not None:
        symbols = load_symbols(symbols_file)

        if not symbols:
            raise ValueError(
                "explicit futures symbols file contains no symbols"
            )

        return FuturesScanSelection(
            symbols=symbols,
            screening=None,
        )

    contracts = filter_futures_universe(
        universe_provider.fetch_futures_contracts(),
        quote_asset=quote_asset,
        blacklist=blacklist,
        allowlist=allowlist,
    )

    if not contracts:
        raise ValueError(
            "no eligible futures contracts were discovered"
        )

    screening = screen_futures_universe(
        contracts,
        screener_provider.fetch_futures_tickers(),
        config,
    )

    symbols = tuple(
        candidate.contract.symbol
        for candidate in screening.candidates
    )

    if not symbols:
        raise ValueError(
            "lightweight futures screening produced no eligible symbols"
        )

    return FuturesScanSelection(
        symbols=symbols,
        screening=screening,
    )


def serialize_futures_screening(
    result: FuturesScreeningResult,
) -> dict[str, object]:
    """Serialize lightweight screening diagnostics for scan output."""

    return {
        "total_contracts": result.total_contracts,
        "total_tickers": result.total_tickers,
        "shortlisted_count": result.shortlisted_count,
        "candidates": [
            {
                "rank": candidate.rank,
                "symbol": candidate.contract.symbol,
                "exchange_symbol": (
                    candidate.contract.exchange_symbol
                ),
                "quote_volume_24h": (
                    candidate.ticker.quote_volume_24h
                ),
                "price_change_percentage_24h": (
                    candidate.ticker
                    .price_change_percentage_24h
                ),
                "absolute_movement_percentage": (
                    candidate.ticker
                    .absolute_movement_percentage
                ),
                "spread_percentage": (
                    candidate.ticker.spread_percentage
                ),
            }
            for candidate in result.candidates
        ],
        "exclusions": [
            {
                "exchange_symbol": exclusion.exchange_symbol,
                "reason": exclusion.reason.value,
                "detail": exclusion.detail,
            }
            for exclusion in result.exclusions
        ],
    }
