"""Application service for user-selected futures market analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from apex.application.decision_analysis import SymbolAnalysis, analyze_symbol
from apex.application.methodology_geometry_enforcement import GeometrySafetyGateMode
from apex.application.methodology_geometry_runtime import GeometryExecutionCosts
from apex.application.opportunity_portfolio import AnalysisMode
from apex.application.symbols import normalize_market_symbol
from apex.config.methodology import MethodologySettings
from apex.config.settings import PrecisionGateSettings, TimeframeIndicatorSettings
from apex.data.providers.base import MarketDataProvider
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig


def analyze_selected_symbol(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    timeframe_indicator_profiles: Mapping[str, TimeframeIndicatorSettings] | None = None,
    candle_limit: int = 200,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    methodology_gate_mode: str = "shadow",
    methodology_settings: MethodologySettings | None = None,
    geometry_safety_mode: GeometrySafetyGateMode | str = GeometrySafetyGateMode.SHADOW,
    geometry_execution_costs: GeometryExecutionCosts | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
    futures_evidence_enabled: bool = True,
    previous_market_regime: str | None = None,
    precision_gate_settings: PrecisionGateSettings | None = None,
) -> SymbolAnalysis:
    """Normalize a user-entered symbol and run the shared discovery pipeline."""

    normalized_symbol = normalize_market_symbol(symbol)
    kwargs: dict[str, Any] = {
        "timeframes": timeframes,
        "timeframe_roles": timeframe_roles,
        "timeframe_max_staleness_seconds": timeframe_max_staleness_seconds,
        "candle_limit": candle_limit,
        "generated_at": generated_at,
        "strategy_routing": strategy_routing,
        "methodology_gate_mode": methodology_gate_mode,
        "methodology_settings": methodology_settings,
        "geometry_safety_mode": geometry_safety_mode,
        "geometry_execution_costs": geometry_execution_costs,
        "market_environment_config": market_environment_config,
        "analysis_mode": AnalysisMode.ANALYZE_FULL,
    }
    if precision_gate_settings is not None:
        kwargs["precision_gate_settings"] = precision_gate_settings
    if previous_market_regime is not None:
        kwargs["previous_market_regime"] = previous_market_regime
    if timeframe_indicator_profiles is not None:
        kwargs["timeframe_indicator_profiles"] = timeframe_indicator_profiles
    if not futures_evidence_enabled:
        kwargs["futures_evidence_enabled"] = False
    return analyze_symbol(normalized_symbol, provider, **kwargs)


__all__ = ["analyze_selected_symbol"]
