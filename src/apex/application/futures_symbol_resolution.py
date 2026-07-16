"""Resolve the active futures scan universe."""

from __future__ import annotations

from pathlib import Path

from apex.application.analysis import load_symbols
from apex.application.futures_universe import futures_universe_symbols
from apex.data.providers.base import FuturesUniverseProvider


def resolve_futures_symbols(
    provider: FuturesUniverseProvider,
    *,
    symbols_file: Path | None = None,
    quote_asset: str = "USDT",
    blacklist: tuple[str, ...] = (),
    allowlist: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Resolve either an explicit static override or the live exchange universe."""

    if symbols_file is not None:
        return load_symbols(symbols_file)

    symbols = futures_universe_symbols(
        provider.fetch_futures_contracts(),
        quote_asset=quote_asset,
        blacklist=blacklist,
        allowlist=allowlist,
    )
    if not symbols:
        raise ValueError("no eligible futures contracts were discovered")
    return symbols
