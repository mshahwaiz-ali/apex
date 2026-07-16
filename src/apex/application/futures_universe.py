"""Deterministic futures-contract universe filtering."""

from __future__ import annotations

from collections.abc import Iterable

from apex.domain.futures_market import FuturesContractMetadata


def filter_futures_universe(
    contracts: Iterable[FuturesContractMetadata],
    *,
    quote_asset: str = "USDT",
    blacklist: Iterable[str] = (),
    allowlist: Iterable[str] | None = None,
) -> tuple[FuturesContractMetadata, ...]:
    """Return active perpetual contracts matching configured universe rules."""

    normalized_quote = quote_asset.strip().upper()
    if not normalized_quote:
        raise ValueError("quote_asset cannot be empty")

    blocked = {_normalize_symbol(value) for value in blacklist}
    allowed = (
        {_normalize_symbol(value) for value in allowlist}
        if allowlist is not None
        else None
    )

    selected: dict[str, FuturesContractMetadata] = {}

    for contract in contracts:
        symbol_key = _normalize_symbol(contract.exchange_symbol)

        if contract.quote_asset.upper() != normalized_quote:
            continue
        if contract.contract_type.upper() != "PERPETUAL":
            continue
        if contract.status.upper() != "TRADING":
            continue
        if symbol_key in blocked:
            continue
        if allowed is not None and symbol_key not in allowed:
            continue

        selected[symbol_key] = contract

    return tuple(
        selected[key]
        for key in sorted(selected)
    )


def futures_universe_symbols(
    contracts: Iterable[FuturesContractMetadata],
    *,
    quote_asset: str = "USDT",
    blacklist: Iterable[str] = (),
    allowlist: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Return normalized display symbols for the selected futures universe."""

    return tuple(
        contract.symbol
        for contract in filter_futures_universe(
            contracts,
            quote_asset=quote_asset,
            blacklist=blacklist,
            allowlist=allowlist,
        )
    )


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper().replace("/", "").replace("-", "")
    if not normalized:
        raise ValueError("symbol filter cannot be empty")
    return normalized
