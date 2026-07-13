"""Normalization and validation for user-selected market symbols."""

from __future__ import annotations

import re
from collections.abc import Iterable

_SYMBOL_PART = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")
DEFAULT_QUOTE_ASSETS: tuple[str, ...] = ("USDT", "USDC", "USD", "BTC", "ETH", "BNB")


def normalize_market_symbol(
    value: str,
    *,
    quote_assets: Iterable[str] = DEFAULT_QUOTE_ASSETS,
) -> str:
    """Return a canonical ``BASE/QUOTE`` symbol for manual analysis.

    Slashed symbols are normalized directly. Compact symbols such as ``BTCUSDT``
    are accepted only when exactly one configured quote suffix matches, avoiding
    silent reinterpretation of ambiguous user input.
    """

    normalized = value.strip().upper().replace(" ", "")
    if not normalized:
        raise ValueError("market symbol cannot be empty")

    if "/" in normalized:
        if normalized.count("/") != 1:
            raise ValueError("market symbol must contain exactly one '/' separator")
        base, quote = normalized.split("/", maxsplit=1)
        return _validate_parts(base, quote)

    quotes = tuple(
        sorted(
            {str(quote).strip().upper() for quote in quote_assets if str(quote).strip()},
            key=len,
            reverse=True,
        )
    )
    matches = tuple(quote for quote in quotes if normalized.endswith(quote))
    if not matches:
        raise ValueError(
            "compact market symbol must end with a configured quote asset; "
            "use BASE/QUOTE form for unusual markets"
        )

    longest_length = len(matches[0])
    longest_matches = tuple(quote for quote in matches if len(quote) == longest_length)
    if len(longest_matches) != 1:
        raise ValueError("compact market symbol is ambiguous; use BASE/QUOTE form")

    quote = longest_matches[0]
    base = normalized[: -len(quote)]
    return _validate_parts(base, quote)


def _validate_parts(base: str, quote: str) -> str:
    if not base or not quote:
        raise ValueError("market symbol requires both base and quote assets")
    if base == quote:
        raise ValueError("base and quote assets must be different")
    if not _SYMBOL_PART.fullmatch(base):
        raise ValueError(f"invalid base asset: {base!r}")
    if not _SYMBOL_PART.fullmatch(quote):
        raise ValueError(f"invalid quote asset: {quote!r}")
    return f"{base}/{quote}"
