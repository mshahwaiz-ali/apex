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
    allowed = {_normalize_symbol(value) for value in allowlist} if allowlist is not None else None

    eligible = sorted(
        (
            contract
            for contract in contracts
            if contract.quote_asset.upper() == normalized_quote
            and contract.contract_type.upper() == "PERPETUAL"
            and contract.status.upper() == "TRADING"
        ),
        key=_contract_sort_key,
    )
    selected: dict[str, FuturesContractMetadata] = {}

    for contract in eligible:
        symbol_key = _normalize_symbol(contract.exchange_symbol)
        if symbol_key in blocked:
            continue
        if allowed is not None and symbol_key not in allowed:
            continue
        selected.setdefault(symbol_key, contract)

    return tuple(selected[key] for key in sorted(selected))


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


def _contract_sort_key(contract: FuturesContractMetadata) -> tuple[str, str, str, str, str]:
    return (
        _normalize_symbol(contract.exchange_symbol),
        contract.symbol.strip().upper(),
        contract.base_asset.strip().upper(),
        contract.quote_asset.strip().upper(),
        contract.contract_type.strip().upper(),
    )


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper().replace("/", "").replace("-", "")
    if not normalized:
        raise ValueError("symbol filter cannot be empty")
    return normalized
