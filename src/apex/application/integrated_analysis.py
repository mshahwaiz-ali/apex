"""Market-environment-aware wrappers for live analysis and scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application import analysis as _analysis
from apex.application.market_strategy_router import route_market_strategies
from apex.application.market_state import (
    MarketStateSnapshot,
    classify_market_state,
    market_state_payload,
)
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    LiquidationClusterSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)
from apex.market_environment import (
    DEFAULT_MARKET_ENVIRONMENT_CONFIG,
    MarketEnvironment,
    MarketEnvironmentConfig,
    build_market_environment,
    market_environment_payload,
)
from apex.risk import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig


@dataclass(frozen=True, slots=True)
class SymbolAnalysis(_analysis.SymbolAnalysis):
    """Base analysis enriched with deterministic multi-timeframe fusion."""

    market_environment: MarketEnvironment | None = None
    market_state: MarketStateSnapshot | None = None


ScanResult = _analysis.ScanResult
load_default_risk_config = _analysis.load_default_risk_config
load_symbols = _analysis.load_symbols
write_json_report = _analysis.write_json_report


class _CachingMarketDataProvider:
    """Cache one analysis pass so fusion does not duplicate provider requests."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider
        self._candles: dict[tuple[str, str, int], list[Candle]] = {}
        self._ticker: dict[str, TickerSnapshot] = {}
        self._order_book: dict[str, OrderBookSnapshot] = {}
        self._exchange_filters: dict[str, ExchangeFilterSnapshot] = {}
        self._liquidation_clusters: dict[str, LiquidationClusterSnapshot] = {}

    @property
    def name(self) -> str:
        return self._provider.name

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        key = (symbol, timeframe, limit)
        if key not in self._candles:
            self._candles[key] = list(self._provider.fetch_candles(symbol, timeframe, limit))
        return list(self._candles[key])

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        if symbol not in self._ticker:
            self._ticker[symbol] = self._provider.fetch_ticker(symbol)
        return self._ticker[symbol]

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        del depth
        if symbol not in self._order_book:
            method = getattr(self._provider, "fetch_order_book")
            self._order_book[symbol] = method(symbol)
        return self._order_book[symbol]

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        if symbol not in self._exchange_filters:
            method = getattr(self._provider, "fetch_exchange_filters")
            self._exchange_filters[symbol] = method(symbol)
        return self._exchange_filters[symbol]

    def fetch_liquidation_clusters(self, symbol: str) -> LiquidationClusterSnapshot:
        if symbol not in self._liquidation_clusters:
            method = getattr(self._provider, "fetch_liquidation_clusters")
            self._liquidation_clusters[symbol] = method(symbol)
        return self._liquidation_clusters[symbol]


def analyze_symbol(
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
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> SymbolAnalysis:
    """Run base analysis and attach one fused market-environment result."""

    decision_time = generated_at or datetime.now(UTC)
    cached_provider = _CachingMarketDataProvider(provider)
    context, _ = _analysis.build_strategy_context(
        symbol,
        cached_provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        received_at=decision_time,
    )
    environment = build_market_environment(context, config=market_environment_config)
    market_strategy_route = route_market_strategies(environment)
    base = _analysis.analyze_symbol(
        symbol,
        cached_provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        risk_config=risk_config,
        exposure=exposure,
        generated_at=decision_time,
        strategy_routing=strategy_routing,
        market_strategy_route=market_strategy_route,
    )
    routing = base.strategy_routing or {}
    decision_regime = routing.get("decision_regime")
    market_state = (
        classify_market_state(
            decision_regime=str(decision_regime),
            environment=environment,
        )
        if environment is not None and isinstance(decision_regime, str)
        else None
    )
    return SymbolAnalysis(
        symbol=base.symbol,
        generated_at=base.generated_at,
        assessment=base.assessment,
        candidate_count=base.candidate_count,
        evaluated_timeframes=base.evaluated_timeframes,
        regime_by_timeframe=base.regime_by_timeframe,
        data_quality_by_timeframe=base.data_quality_by_timeframe,
        strategy_routing=base.strategy_routing,
        precision_entry=base.precision_entry,
        phase5_diagnostics=base.phase5_diagnostics,
        candidate_ranking=base.candidate_ranking,
        risk_rejection_diagnostics=base.risk_rejection_diagnostics,
        market_environment=environment,
        market_state=market_state,
    )


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    risk_config: RiskConfig = DEFAULT_RISK_CONFIG,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> ScanResult:
    """Analyze each symbol once with environment-aware results."""

    timestamp = generated_at or datetime.now(UTC)
    analyses: list[SymbolAnalysis] = []
    failures: dict[str, str] = {}

    for symbol in symbols:
        try:
            analyses.append(
                analyze_symbol(
                    symbol,
                    provider,
                    timeframes=timeframes,
                    timeframe_roles=timeframe_roles,
                    timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
                    candle_limit=candle_limit,
                    risk_config=risk_config,
                    generated_at=timestamp,
                    strategy_routing=strategy_routing,
                    market_environment_config=market_environment_config,
                )
            )
        except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
            failures[symbol] = str(exc)

    return ScanResult(
        generated_at=timestamp,
        analyses=tuple(sorted(analyses, key=_scan_sort_key)),
        failures=failures,
    )


def serialize_symbol_analysis(analysis: _analysis.SymbolAnalysis) -> dict[str, Any]:
    """Serialize base analysis plus the fused environment when available."""

    payload = _analysis.serialize_symbol_analysis(analysis)
    environment = getattr(analysis, "market_environment", None)
    payload["market_environment"] = (
        market_environment_payload(environment) if isinstance(environment, MarketEnvironment) else None
    )
    market_state = getattr(analysis, "market_state", None)
    payload["market_state"] = (
        market_state_payload(market_state)
        if isinstance(market_state, MarketStateSnapshot)
        else None
    )
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    """Return scanner JSON with environment-aware nested analyses."""

    approved = tuple(item for item in result.analyses if item.assessment.setup is not None)
    long_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None
        and item.assessment.setup.direction.value == "long"
    )
    short_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None
        and item.assessment.setup.direction.value == "short"
    )
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "top_long_setups": [serialize_symbol_analysis(item) for item in long_setups],
        "top_short_setups": [serialize_symbol_analysis(item) for item in short_setups],
        "results": [serialize_symbol_analysis(item) for item in result.analyses],
        "failures": dict(result.failures),
    }


def format_symbol_text(analysis: _analysis.SymbolAnalysis) -> str:
    """Format an operational analysis summary including market environment."""

    base_text = _analysis.format_symbol_text(analysis)
    environment = getattr(analysis, "market_environment", None)
    if not isinstance(environment, MarketEnvironment):
        return base_text
    warnings = ", ".join(environment.reason_codes) if environment.reason_codes else "none"
    return "\n".join(
        (
            base_text,
            f"Regime: {environment.primary_regime.value}",
            f"HTF bias: {environment.higher_timeframe_bias.value}",
            f"Execution / entry: {environment.execution_timeframe} / {environment.entry_timeframe}",
            f"Alignment / conflict: {environment.alignment_score:.1f} / {environment.conflict_score:.1f}",
            f"Volatility / extension: {environment.volatility_state.value} / {environment.extension_state.value}",
            f"Long / short suitability: {environment.long_suitability_score:.1f} / {environment.short_suitability_score:.1f}",
            f"Tradeable: {'yes' if environment.tradeable else 'no'}",
            f"Warnings: {warnings}",
        )
    )


def format_scan_text(result: ScanResult) -> str:
    """Return environment-aware human-readable scanner output."""

    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    for analysis in result.analyses:
        lines.append(format_symbol_text(analysis))
    for symbol, reason in result.failures.items():
        lines.append(f"{symbol}: FAILED | {reason}")
    return "\n".join(lines)


def _scan_sort_key(analysis: _analysis.SymbolAnalysis) -> tuple[int, float, float, str]:
    setup = analysis.assessment.setup
    if setup is None:
        return (1, 0.0, 0.0, analysis.symbol)
    max_risk_reward = max(target.risk_reward for target in setup.take_profits)
    return (0, -setup.confidence_score, -max_risk_reward, analysis.symbol)
