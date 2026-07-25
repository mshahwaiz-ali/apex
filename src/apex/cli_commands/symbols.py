"""CLI symbol normalisation for Binance-style USDT futures markets."""

from __future__ import annotations

DEFAULT_QUOTE_ASSET = "USDT"


def normalize_futures_symbol(value: str, *, quote_asset: str = DEFAULT_QUOTE_ASSET) -> str:
    """Return a canonical ``BASE/QUOTE`` futures symbol.

    Examples:
        ``bank`` -> ``BANK/USDT``
        ``bankusdt`` -> ``BANK/USDT``
        ``bank-usdt`` -> ``BANK/USDT``
        ``BANK/USDT`` -> ``BANK/USDT``
    """

    normalized_quote = quote_asset.strip().upper()
    if not normalized_quote:
        raise ValueError("quote asset cannot be blank")

    raw = value.strip().upper()
    if not raw:
        raise ValueError("symbol cannot be blank")

    compact = raw.replace("-", "/").replace("_", "/").replace(":", "/")
    if "/" in compact:
        parts = tuple(part for part in compact.split("/") if part)
        if len(parts) != 2:
            raise ValueError("symbol must use BASE/QUOTE format")
        base, quote = parts
    elif compact.endswith(normalized_quote) and len(compact) > len(normalized_quote):
        base = compact[: -len(normalized_quote)]
        quote = normalized_quote
    else:
        base = compact
        quote = normalized_quote

    if not base or not quote:
        raise ValueError("symbol must contain both base and quote assets")
    return f"{base}/{quote}"


__all__ = ["DEFAULT_QUOTE_ASSET", "normalize_futures_symbol"]
