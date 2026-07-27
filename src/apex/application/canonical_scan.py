"""Canonical scan orchestration with selected-symbol analysis parity."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime

from apex.application.discovery_contracts import ScanResult
from apex.application.methodology_geometry_enforcement import GeometrySafetyGateMode
from apex.application.methodology_geometry_runtime import GeometryExecutionCosts
from apex.application.selected_symbol import analyze_selected_symbol
from apex.config.methodology import MethodologySettings
from apex.config.settings import TimeframeIndicatorSettings
from apex.data.providers.base import MarketDataProvider
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    timeframe_indicator_profiles: Mapping[str, TimeframeIndicatorSettings] | None = None,
    candle_limit: int = 200,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
    methodology_gate_mode: str = "shadow",
    methodology_settings: MethodologySettings | None = None,
    geometry_safety_mode: GeometrySafetyGateMode | str = GeometrySafetyGateMode.SHADOW,
    geometry_execution_costs: GeometryExecutionCosts | None = None,
    futures_evidence_enabled: bool = True,
    previous_market_regimes: Mapping[str, str] | None = None,
) -> ScanResult:
    """Analyze every shortlisted symbol with the same full authority as ``analyze``.

    Scan differs from selected-symbol analysis only in symbol selection and
    per-symbol failure isolation. It must not use a reduced opportunity mode that
    can hide activation-blocked, future, or re-entry plans from the canonical
    portfolio.
    """

    timestamp = generated_at or datetime.now(UTC)
    analyses = []
    failures: dict[str, str] = {}
    for symbol in symbols:
        try:
            analyses.append(
                analyze_selected_symbol(
                    symbol,
                    provider,
                    timeframes=timeframes,
                    timeframe_roles=timeframe_roles,
                    timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
                    timeframe_indicator_profiles=timeframe_indicator_profiles,
                    candle_limit=candle_limit,
                    generated_at=timestamp,
                    strategy_routing=strategy_routing,
                    methodology_gate_mode=methodology_gate_mode,
                    methodology_settings=methodology_settings,
                    geometry_safety_mode=geometry_safety_mode,
                    geometry_execution_costs=geometry_execution_costs,
                    market_environment_config=market_environment_config,
                    futures_evidence_enabled=futures_evidence_enabled,
                    previous_market_regime=(
                        None
                        if previous_market_regimes is None
                        else previous_market_regimes.get(symbol.upper())
                    ),
                )
            )
        except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
            failures[symbol] = str(exc)

    return ScanResult(
        generated_at=timestamp,
        analyses=tuple(analyses),
        failures=failures,
    )


__all__ = ["scan_symbols"]
