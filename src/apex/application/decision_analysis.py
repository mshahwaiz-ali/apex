"""Strategy-routing and near-current-entry orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.application import analysis as _analysis
from apex.application import integrated_analysis as _integrated
from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    market_strategy_route_payload,
    route_market_strategies,
)
from apex.application.near_current_entry import (
    NearCurrentEntryDecision,
    evaluate_near_current_entry,
    near_current_entry_payload,
)
from apex.data.providers.base import MarketDataProvider
from apex.domain import GainerStateThresholds, MarketCategory, ScannerMode
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig
from apex.risk import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig


@dataclass(frozen=True, slots=True)
class SymbolAnalysis(_integrated.SymbolAnalysis):
    """Integrated analysis enriched with environment routing and entry actionability."""

    market_strategy_route: MarketStrategyRoute | None = None
    near_current_entry: NearCurrentEntryDecision | None = None


ScanResult = _analysis.ScanResult
load_default_risk_config = _integrated.load_default_risk_config
load_symbols = _integrated.load_symbols
write_json_report = _integrated.write_json_report


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
    scanner_type: MarketCategory = MarketCategory.NORMAL_MARKET,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    gainer_state_thresholds: GainerStateThresholds | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> SymbolAnalysis:
    """Run integrated analysis and attach routing and entry decisions."""

    base = _integrated.analyze_symbol(
        symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        risk_config=risk_config,
        exposure=exposure,
        generated_at=generated_at,
        scanner_type=scanner_type,
        strategy_routing=strategy_routing,
        gainer_state_thresholds=gainer_state_thresholds,
        market_environment_config=market_environment_config,
    )
    environment = base.market_environment
    route = route_market_strategies(environment) if environment is not None else None
    setup = base.assessment.setup
    near_entry = (
        evaluate_near_current_entry(
            base.precision_entry,
            environment,
            route,
            selected_strategy=setup.strategy if setup is not None else None,
            selected_direction=setup.direction if setup is not None else None,
        )
        if environment is not None and route is not None
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
        scanner_type=base.scanner_type,
        gainer_state=base.gainer_state,
        gainer_evidence=base.gainer_evidence,
        strategy_routing=base.strategy_routing,
        precision_entry=base.precision_entry,
        phase5_diagnostics=base.phase5_diagnostics,
        risk_rejection_diagnostics=base.risk_rejection_diagnostics,
        market_environment=environment,
        market_strategy_route=route,
        near_current_entry=near_entry,
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
    scanner_mode: ScannerMode | str = ScannerMode.NORMAL,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    gainer_state_thresholds: GainerStateThresholds | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> ScanResult:
    """Analyze scanner symbols with routing and entry decisions."""

    timestamp = generated_at or datetime.now(UTC)
    mode = scanner_mode if isinstance(scanner_mode, ScannerMode) else ScannerMode(scanner_mode)
    analyses: list[_analysis.SymbolAnalysis] = []
    failures: dict[str, str] = {}
    for scanner_type in _scanner_categories(mode):
        for symbol in symbols:
            failure_key = symbol if mode is ScannerMode.NORMAL else f"{scanner_type.value}:{symbol}"
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
                        scanner_type=scanner_type,
                        strategy_routing=strategy_routing,
                        gainer_state_thresholds=gainer_state_thresholds,
                        market_environment_config=market_environment_config,
                    )
                )
            except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
                failures[failure_key] = str(exc)
    return ScanResult(
        generated_at=timestamp,
        analyses=tuple(sorted(analyses, key=_scan_sort_key)),
        failures=failures,
        scanner_mode=mode,
    )


def serialize_symbol_analysis(analysis: _analysis.SymbolAnalysis) -> dict[str, Any]:
    """Serialize analysis with route and near-current entry overlays."""

    payload = _integrated.serialize_symbol_analysis(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    near_entry = getattr(analysis, "near_current_entry", None)
    payload["market_strategy_route"] = (
        market_strategy_route_payload(route) if isinstance(route, MarketStrategyRoute) else None
    )
    payload["near_current_entry"] = (
        near_current_entry_payload(near_entry) if isinstance(near_entry, NearCurrentEntryDecision) else None
    )
    payload["decision_reason_code"] = _decision_reason_code(analysis, near_entry)
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    """Return scanner JSON with decision-aware nested analyses."""

    approved = tuple(item for item in result.analyses if item.assessment.setup is not None)
    normal = tuple(item for item in approved if item.scanner_type is MarketCategory.NORMAL_MARKET)
    gainers = tuple(item for item in approved if item.scanner_type is MarketCategory.GAINER)
    long_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "long"
    )
    short_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "short"
    )
    return {
        "generated_at": result.generated_at.isoformat(),
        "scanner_mode": result.scanner_mode.value,
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "best_normal_market": serialize_symbol_analysis(normal[0]) if normal else None,
        "best_gainer": serialize_symbol_analysis(gainers[0]) if gainers else None,
        "top_long_setups": [serialize_symbol_analysis(item) for item in long_setups],
        "top_short_setups": [serialize_symbol_analysis(item) for item in short_setups],
        "results": [serialize_symbol_analysis(item) for item in result.analyses],
        "failures": dict(result.failures),
    }


def format_symbol_text(analysis: _analysis.SymbolAnalysis) -> str:
    """Format analysis with explicit scanner, pipeline, and actionability stages."""

    base_text = _integrated.format_symbol_text(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    near_entry = getattr(analysis, "near_current_entry", None)
    environment = getattr(analysis, "market_environment", None)
    scanner = _scanner_label(analysis.scanner_type)
    decision = (
        "NO_TRADE"
        if analysis.assessment.setup is None
        else analysis.assessment.setup.direction.value.upper()
    )
    lines = [f"{analysis.symbol} | {scanner} | {decision}", base_text]
    if isinstance(route, MarketStrategyRoute):
        strategies = ", ".join(item.value for item in route.strategy_priority) or "none"
        lines.extend(
            (
                f"Environment tradeable: {'yes' if environment is not None and environment.tradeable else 'no'}",
                f"Strategy routed: {strategies}",
                f"Preferred direction: {route.preferred_direction.value}",
                f"Routing score: {route.routing_score:.1f}",
            )
        )
    phase5 = analysis.phase5_diagnostics or {}
    lines.extend(
        (
            f"Raw candidates: {analysis.candidate_count}",
            f"Phase 5 accepted selection: {'yes' if phase5.get('selected') else 'no'}",
            f"Decision reason: {_decision_reason_code(analysis, near_entry)}",
        )
    )
    if isinstance(near_entry, NearCurrentEntryDecision):
        quality = (
            f"{near_entry.entry_quality_score:.1f}"
            if near_entry.entry_quality_score is not None
            else "unavailable"
        )
        chase = near_entry.chase_risk.value if near_entry.chase_risk is not None else "unavailable"
        lines.extend(
            (
                f"Entry state: {near_entry.entry_state}",
                f"Entry quality / chase: {quality} / {chase}",
                f"Actionable now: {'yes' if near_entry.actionable_now else 'no'}",
            )
        )
        if near_entry.reasons:
            lines.append(f"Current condition: {near_entry.reasons[0]}")
    return "\n".join(lines)


def format_scan_text(result: ScanResult) -> str:
    """Return decision-aware human-readable scanner output."""

    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    lines.extend(format_symbol_text(analysis) for analysis in result.analyses)
    lines.extend(f"{symbol}: FAILED | {reason}" for symbol, reason in result.failures.items())
    return "\n".join(lines)


def _decision_reason_code(
    analysis: _analysis.SymbolAnalysis,
    near_entry: NearCurrentEntryDecision | None,
) -> str:
    environment = getattr(analysis, "market_environment", None)
    route = getattr(analysis, "market_strategy_route", None)
    phase5 = analysis.phase5_diagnostics or {}
    if environment is not None and not environment.tradeable:
        return "ENVIRONMENT_BLOCKED"
    if route is not None and not route.strategy_priority:
        return "NO_ROUTED_STRATEGY"
    if analysis.candidate_count == 0:
        return "NO_CANDIDATE_GENERATED"
    if not phase5.get("selected"):
        return "CANDIDATE_REJECTED"
    if near_entry is not None and near_entry.entry_state in {
        "WAIT_FOR_RECLAIM",
        "WAIT_FOR_RETEST",
        "APPROACHING_ENTRY",
        "MISSED_ENTRY",
        "INVALIDATED",
    }:
        return near_entry.entry_state
    return (
        "NO_TRADE"
        if analysis.assessment.setup is None
        else near_entry.entry_state
        if near_entry
        else "NO_TRADE"
    )


def _scanner_label(scanner_type: MarketCategory) -> str:
    if scanner_type is MarketCategory.NORMAL_MARKET:
        return "NORMAL"
    return "GAINER"


def _scanner_categories(mode: ScannerMode) -> tuple[MarketCategory, ...]:
    if mode is ScannerMode.NORMAL:
        return (MarketCategory.NORMAL_MARKET,)
    if mode is ScannerMode.GAINERS:
        return (MarketCategory.GAINER,)
    return (MarketCategory.NORMAL_MARKET, MarketCategory.GAINER)


def _scan_sort_key(analysis: _analysis.SymbolAnalysis) -> tuple[int, float, float, str, str]:
    setup = analysis.assessment.setup
    scanner = analysis.scanner_type.value
    if setup is None:
        return (1, 0.0, 0.0, analysis.symbol, scanner)
    max_risk_reward = max(target.risk_reward for target in setup.take_profits)
    return (0, -setup.confidence_score, -max_risk_reward, analysis.symbol, scanner)
