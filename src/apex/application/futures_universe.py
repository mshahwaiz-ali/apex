"""Deterministic futures-contract universe filtering."""

from __future__ import annotations

from collections.abc import Iterable

from apex.domain.futures_market import FuturesContractMetadata


def filter_futures_universe(
    contracts: Iterable[FuturesContractMetadata],
    *,
    quote_asset: str = "USDT",
    blacklist: Iterable[str] = (),
    allowlist: Iterable[str