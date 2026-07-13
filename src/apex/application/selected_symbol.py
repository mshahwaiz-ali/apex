"""Application service for user-selected market analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from apex.application.analysis import SymbolAnalysis, analyze_symbol
from apex.application.symbols import normalize_market_symbol
from apex.data.providers.base import MarketDataProvider
from apex.risk import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig


def analyze_selected_symbol(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    risk_config: RiskConfig = DEFAULT_RISK_CONFIG,
    exposure: ExposureState | None = None,
    generated_at: datetime | None = None,
) -> SymbolAnalysis:
    """Normalize a user-entered symbol and run the standard analysis pipeline."""

    normalized_symbol = normalize_market_symbol(symbol)
    return analyze_symbol(
        normalized_symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        risk_config=risk_config,
        exposure=exposure,
        generated_at=generated_at,
    )
