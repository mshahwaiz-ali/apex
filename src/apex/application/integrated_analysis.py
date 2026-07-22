"""Market-environment-aware wrappers for live discovery analysis and scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from apex.application import discovery_analysis as _analysis
from apex.application.discovery_analysis import (
    format_symbol_text as format_discovery_symbol_text,
)
from apex.application.discovery_analysis import (
    serialize_symbol_analysis as serialize_discovery_symbol_analysis,
)
from apex.application.discovery_context import build_strategy_context
from apex.application.discovery_contracts import ScanResult
from apex.application.discovery_contracts import SymbolAnalysis as DiscoverySymbolAnalysis
from apex.application.market_state import (
    MarketStateSnapshot,
    classify_market_state,
    market_state_payload,
)
from apex.application.market_strategy_router import route_market_strategies
from apex.application.methodology_geometry_enforcement import GeometrySafetyGateMode
from apex.application.methodology_geometry_runtime import GeometryExecutionCosts
from apex.application.methodology_market_state import adapt_market_state
from apex.application.opportunity_portfolio import AnalysisMode
from apex.application.symbols import load_symbol_file
from apex.config.methodology import MethodologySettings
from apex.config.settings import TimeframeIndicatorSettings
from apex.data.providers.base import FuturesEvidenceProvider, MarketDataProvider
from apex.domain.futures_evidence import (
    FundingRateSnapshot,
    OpenInterestSnapshot,
    PremiumIndexSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
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
from apex.structure.regime import classify_market_regime


@dataclass(frozen=True, slots=True)
class SymbolAnalysis(DiscoverySymbolAnalysis):
    """Discovery analysis enriched with deterministic multi-timeframe fusion."""

    market_environment: MarketEnvironment | None = None
    market_state: MarketStateSnapshot | None = None


load_symbols = load_symbol_file
write_json_report = _analysis.write_json_report


class _CachingMarketDataProvider:
    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider
        self._candles: dict[tuple[str, str, int], list[Candle]] = {}
        self._ticker: dict[str, TickerSnapshot] = {}
        self._order_book: dict[tuple[str, int], OrderBookSnapshot] = {}
        self._exchange_filters: dict[str, ExchangeFilterSnapshot] = {}
        self._funding: dict[tuple[str, int], tuple[FundingRateSnapshot, ...]] = {}
        self._open_interest: dict[tuple[str, str, int], tuple[OpenInterestSnapshot, ...]] = {}
        self._taker_flow: dict[tuple[str, str, int], tuple[TakerFlowSnapshot, ...]] = {}
        self._premium_index: dict[str, PremiumIndexSnapshot] = {}

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
        key = (symbol, depth)
        if key not in self._order_book:
            fetch_order_book = getattr(self._provider, "fetch_order_book", None)
            if not callable(fetch_order_book):
                raise AttributeError("market-data provider does not support order books")
            snapshot = fetch_order_book(symbol, depth)
            if not isinstance(snapshot, OrderBookSnapshot):
                raise TypeError("market-data provider returned an invalid order book snapshot")
            self._order_book[key] = snapshot
        return self._order_book[key]

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        if symbol not in self._exchange_filters:
            fetch_exchange_filters = getattr(self._provider, "fetch_exchange_filters", None)
            if not callable(fetch_exchange_filters):
                raise AttributeError("market-data provider does not support exchange filters")
            snapshot = fetch_exchange_filters(symbol)
            if not isinstance(snapshot, ExchangeFilterSnapshot):
                raise TypeError("market-data provider returned invalid exchange filters")
            self._exchange_filters[symbol] = snapshot
        return self._exchange_filters[symbol]

    def fetch_funding_rates(self, symbol: str, limit: int = 100) -> tuple[FundingRateSnapshot, ...]:
        key = (symbol, limit)
        if key not in self._funding:
            evidence = cast(FuturesEvidenceProvider, self._provider)
            self._funding[key] = tuple(evidence.fetch_funding_rates(symbol, limit))
        return self._funding[key]

    def fetch_open_interest_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[OpenInterestSnapshot, ...]:
        key = (symbol, period, limit)
        if key not in self._open_interest:
            evidence = cast(FuturesEvidenceProvider, self._provider)
            self._open_interest[key] = tuple(
                evidence.fetch_open_interest_history(symbol, period, limit)
            )
        return self._open_interest[key]

    def fetch_taker_flow_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[TakerFlowSnapshot, ...]:
        key = (symbol, period, limit)
        if key not in self._taker_flow:
            evidence = cast(FuturesEvidenceProvider, self._provider)
            self._taker_flow[key] = tuple(evidence.fetch_taker_flow_history(symbol, period, limit))
        return self._taker_flow[key]

    def fetch_premium_index(self, symbol: str) -> PremiumIndexSnapshot:
        if symbol not in self._premium_index:
            evidence = cast(FuturesEvidenceProvider, self._provider)
            self._premium_index[symbol] = evidence.fetch_premium_index(symbol)
        return self._premium_index[symbol]


def analyze_symbol(
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
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
    methodology_gate_mode: str = "shadow",
    methodology_settings: MethodologySettings | None = None,
    geometry_safety_mode: GeometrySafetyGateMode | str = GeometrySafetyGateMode.SHADOW,
    geometry_execution_costs: GeometryExecutionCosts | None = None,
    futures_evidence_enabled: bool = True,
    analysis_mode: AnalysisMode = AnalysisMode.ANALYZE_FULL,
) -> SymbolAnalysis:
    """Run discovery and attach fused market environment."""

    decision_time = generated_at or datetime.now(UTC)
    cached = _CachingMarketDataProvider(provider)
    context, _ = build_strategy_context(
        symbol,
        cached,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        timeframe_indicator_profiles=timeframe_indicator_profiles,
        candle_limit=candle_limit,
        received_at=decision_time,
        futures_evidence_enabled=futures_evidence_enabled,
    )
    environment = build_market_environment(context, config=market_environment_config)
    route = route_market_strategies(environment)
    decision_regime = classify_market_regime(context.decision_frame.structure)
    market_state = classify_market_state(
        decision_regime=decision_regime.value,
        environment=environment,
    )
    methodology_state = adapt_market_state(market_state)
    base = _analysis.analyze_symbol(
        symbol,
        cached,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        timeframe_indicator_profiles=timeframe_indicator_profiles,
        candle_limit=candle_limit,
        generated_at=decision_time,
        strategy_routing=strategy_routing,
        market_strategy_route=route,
        methodology_market_state=methodology_state.primary,
        methodology_gate_mode=methodology_gate_mode,
        methodology_settings=methodology_settings,
        geometry_safety_mode=geometry_safety_mode,
        geometry_execution_costs=geometry_execution_costs,
        futures_evidence_enabled=futures_evidence_enabled,
        analysis_mode=analysis_mode,
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
        phase5_diagnostics=base.phase5_diagnostics,
        candidate_ranking=base.candidate_ranking,
        methodology=base.methodology,
        methodology_gate=base.methodology_gate,
        market_intelligence=base.market_intelligence,
        historical_edge=base.historical_edge,
        outcome_candles=base.outcome_candles,
        opportunity_portfolio=base.opportunity_portfolio,
        market_environment=environment,
        market_state=market_state,
    )


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    **kwargs: Any,
) -> ScanResult:
    timestamp = kwargs.pop("generated_at", None) or datetime.now(UTC)
    analyses: list[SymbolAnalysis] = []
    failures: dict[str, str] = {}
    for symbol in symbols:
        try:
            analyses.append(analyze_symbol(symbol, provider, generated_at=timestamp, **kwargs))
        except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
            failures[symbol] = str(exc)
    return ScanResult(timestamp, tuple(sorted(analyses, key=_scan_sort_key)), failures)


def serialize_symbol_analysis(analysis: DiscoverySymbolAnalysis) -> dict[str, Any]:
    payload = serialize_discovery_symbol_analysis(analysis)
    environment = getattr(analysis, "market_environment", None)
    state = getattr(analysis, "market_state", None)
    payload["market_environment"] = (
        market_environment_payload(environment)
        if isinstance(environment, MarketEnvironment)
        else None
    )
    payload["market_state"] = (
        market_state_payload(state) if isinstance(state, MarketStateSnapshot) else None
    )
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    approved = tuple(item for item in result.analyses if item.assessment.setup is not None)
    longs = tuple(
        item
        for item in approved
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "long"
    )
    shorts = tuple(
        item
        for item in approved
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "short"
    )
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "top_long_setups": [serialize_symbol_analysis(item) for item in longs],
        "top_short_setups": [serialize_symbol_analysis(item) for item in shorts],
        "results": [serialize_symbol_analysis(item) for item in result.analyses],
        "failures": dict(result.failures),
    }


def format_symbol_text(analysis: DiscoverySymbolAnalysis) -> str:
    base = format_discovery_symbol_text(analysis)
    environment = getattr(analysis, "market_environment", None)
    if not isinstance(environment, MarketEnvironment):
        return base
    warnings = ", ".join(environment.reason_codes) if environment.reason_codes else "none"
    return "\n".join(
        (
            base,
            f"Regime: {environment.primary_regime.value}",
            f"HTF bias: {environment.higher_timeframe_bias.value}",
            "Alignment / conflict: "
            f"{environment.alignment_score:.1f} / {environment.conflict_score:.1f}",
            "Long / short suitability: "
            f"{environment.long_suitability_score:.1f} / "
            f"{environment.short_suitability_score:.1f}",
            f"Tradeable: {'yes' if environment.tradeable else 'no'}",
            f"Warnings: {warnings}",
        )
    )


def format_scan_text(result: ScanResult) -> str:
    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    lines.extend(format_symbol_text(item) for item in result.analyses)
    lines.extend(f"{symbol}: FAILED | {reason}" for symbol, reason in result.failures.items())
    return "\n".join(lines)


def _scan_sort_key(analysis: DiscoverySymbolAnalysis) -> tuple[int, float, float, str]:
    setup = analysis.assessment.setup
    if setup is None:
        return (1, 0.0, 0.0, analysis.symbol)
    return (
        0,
        -setup.confidence_score,
        -max(target.risk_reward for target in setup.take_profits),
        analysis.symbol,
    )
