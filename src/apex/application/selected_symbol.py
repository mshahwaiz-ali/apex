"""Application service for user-selected futures market analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from apex.application.decision_analysis import SymbolAnalysis, analyze_symbol
from apex.application.symbols import normalize_market_symbol
from apex.data.providers.base import MarketDataProvider


def analyze_selected_symbol(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
) -> SymbolAnalysis:
    """Normalize a user-entered symbol and run the trade-discovery pipeline."""

    normalized_symbol = normalize_market_symbol(symbol)
    return analyze_symbol(
        normalized_symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        generated_at=generated_at,
        strategy_routing=strategy_routing,
    )


__all__ = ["analyze_selected_symbol"]
