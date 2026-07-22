"""Canonical strategy-routing analysis orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from apex.application import integrated_analysis as _integrated
from apex.application.discovery_contracts import (
    ScanResult as DiscoveryScanResult,
)
from apex.application.discovery_contracts import (
    SymbolAnalysis as DiscoverySymbolAnalysis,
)
from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    market_strategy_route_payload,
    route_market_strategies,
)
from apex.application.methodology_geometry_enforcement import GeometrySafetyGateMode
from apex.application.methodology_geometry_runtime import GeometryExecutionCosts
from apex.application.methodology_setup_maturity import derive_setup_maturity
from apex.application.methodology_strategy_contracts import SetupMaturity
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    PortfolioDecisionState,
    SymbolOpportunityPortfolio,
)
from apex.config.methodology import MethodologySettings
from apex.config.settings import TimeframeIndicatorSettings
from apex.data.providers.base import MarketDataProvider
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig

DEFAULT_SCAN_DISPLAY_LIMIT = 15
_UNAVAILABLE_MATURITIES = frozenset(
    {
        SetupMaturity.ENTRY_LATE,
        SetupMaturity.ENTRY_MISSED,
        SetupMaturity.PATTERN_FAILED,
        SetupMaturity.INVALIDATED,
    }
)


@dataclass(frozen=True, slots=True)
class SymbolAnalysis(_integrated.SymbolAnalysis):
    """Integrated discovery analysis enriched with market strategy routing."""

    market_strategy_route: MarketStrategyRoute | None = None


load_symbols = _integrated.load_symbols
write_json_report = _integrated.write_json_report


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
    """Run integrated discovery analysis, routing, and the shared methodology gate."""

    base = _integrated.analyze_symbol(
        symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        timeframe_indicator_profiles=timeframe_indicator_profiles,
        candle_limit=candle_limit + 1,
        generated_at=generated_at,
        strategy_routing=strategy_routing,
        market_environment_config=market_environment_config,
        methodology_gate_mode=methodology_gate_mode,
        methodology_settings=methodology_settings,
        geometry_safety_mode=geometry_safety_mode,
        geometry_execution_costs=geometry_execution_costs,
        futures_evidence_enabled=futures_evidence_enabled,
        analysis_mode=analysis_mode,
    )
    environment = base.market_environment
    route = route_market_strategies(environment) if environment is not None else None
    analysis = SymbolAnalysis(
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
        methodology=getattr(base, "methodology", None),
        methodology_gate=getattr(base, "methodology_gate", None),
        market_intelligence=base.market_intelligence,
        historical_edge=base.historical_edge,
        outcome_candles=base.outcome_candles,
        opportunity_portfolio=base.opportunity_portfolio,
        market_environment=environment,
        market_state=base.market_state,
        market_strategy_route=route,
    )
    # Candidate-specific methodology routing is already enforced inside the
    # canonical discovery core. Reapplying the legacy strategy-level gate here
    # would collapse layered state back into one broad market-state verdict.
    return analysis


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
) -> DiscoveryScanResult:
    """Analyze each symbol once with canonical routing, gating, and ranking."""

    timestamp = generated_at or datetime.now(UTC)
    analyses: list[SymbolAnalysis] = []
    failures: dict[str, str] = {}
    for symbol in symbols:
        try:
            analysis_kwargs: dict[str, Any] = {
                "timeframes": timeframes,
                "timeframe_roles": timeframe_roles,
                "timeframe_max_staleness_seconds": timeframe_max_staleness_seconds,
                "candle_limit": candle_limit,
                "generated_at": timestamp,
                "strategy_routing": strategy_routing,
                "market_environment_config": market_environment_config,
                "methodology_gate_mode": methodology_gate_mode,
                "methodology_settings": methodology_settings,
                "geometry_safety_mode": geometry_safety_mode,
                "geometry_execution_costs": geometry_execution_costs,
                "analysis_mode": AnalysisMode.SCAN_CMP_FIRST,
            }
            if timeframe_indicator_profiles is not None:
                analysis_kwargs["timeframe_indicator_profiles"] = timeframe_indicator_profiles
            if not futures_evidence_enabled:
                analysis_kwargs["futures_evidence_enabled"] = False
            analyses.append(
                analyze_symbol(
                    symbol,
                    provider,
                    **analysis_kwargs,
                )
            )
        except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
            failures[symbol] = str(exc)
    return DiscoveryScanResult(
        generated_at=timestamp,
        analyses=tuple(
            sorted(
                analyses,
                key=lambda item: _scan_sort_key(item),
            )
        ),
        failures=failures,
    )


def serialize_symbol_analysis(analysis: DiscoverySymbolAnalysis) -> dict[str, Any]:
    """Serialize one analysis with canonical strategy routing."""

    payload = _integrated.serialize_symbol_analysis(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    payload["market_strategy_route"] = (
        market_strategy_route_payload(route) if isinstance(route, MarketStrategyRoute) else None
    )
    payload["methodology_gate"] = getattr(analysis, "methodology_gate", None)
    portfolio = _opportunity_portfolio(analysis)
    payload["portfolio_decision"] = None if portfolio is None else portfolio.public_decision.value
    payload["decision_reason_code"] = _decision_reason_code(analysis)
    return payload


def serialize_scan_result(result: DiscoveryScanResult) -> dict[str, Any]:
    """Return scanner JSON with decision-aware nested analyses."""

    displayed = _display_analyses(result)
    approved = tuple(item for item in displayed if _has_portfolio_opportunities(item))
    long_setups = tuple(item for item in approved if _portfolio_has_direction(item, "long"))
    short_setups = tuple(item for item in approved if _portfolio_has_direction(item, "short"))
    serialized_results = [serialize_symbol_analysis(item) for item in displayed]
    opportunity_records = _scan_opportunity_records(displayed)
    return {
        "generated_at": result.generated_at.isoformat(),
        "opportunity_count": len(opportunity_records),
        "opportunities": opportunity_records,
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "top_long_setups": [serialize_symbol_analysis(item) for item in long_setups],
        "top_short_setups": [serialize_symbol_analysis(item) for item in short_setups],
        "results": serialized_results,
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(displayed),
        "display_limit": DEFAULT_SCAN_DISPLAY_LIMIT,
        "failures": dict(result.failures),
    }


def _scan_opportunity_records(
    analyses: Sequence[DiscoverySymbolAnalysis],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for analysis in analyses:
        portfolio = getattr(analysis, "opportunity_portfolio", None)
        if portfolio is None:
            continue
        opportunities = getattr(
            portfolio,
            "opportunities",
            getattr(portfolio, "all_opportunities", ()),
        )
        for opportunity in opportunities:
            records.append(
                {
                    "symbol": analysis.symbol,
                    "opportunity_id": opportunity.opportunity_id,
                    "sequence_role": opportunity.sequence_role.value,
                    "direction": opportunity.setup.direction.value,
                    "strategy": opportunity.setup.strategy.value,
                    "entry_status": opportunity.setup.entry_status.value,
                    "execution_allowed_now": opportunity.setup.execution_allowed_now,
                }
            )
    return records


def _format_portfolio_slot(label: str, opportunity: Any | None) -> str:
    if opportunity is None:
        return f"{label}: none"

    setup = opportunity.setup
    return (
        f"{label}: {setup.direction.value.upper()} | "
        f"{setup.strategy.value} | {setup.entry_status.value} | "
        f"entry {setup.entry.lower:g}-{setup.entry.upper:g} | "
        f"ideal {setup.entry.preferred:g} | stop {setup.stop_loss.price:g}"
    )


def _portfolio_summary_lines(
    analysis: DiscoverySymbolAnalysis,
) -> tuple[str, ...]:
    portfolio = getattr(analysis, "opportunity_portfolio", None)
    if portfolio is None:
        return ()

    lines = [
        f"Opportunity portfolio: {len(portfolio.all_opportunities)}",
        _format_portfolio_slot("Current long", portfolio.current_long),
        _format_portfolio_slot("Current short", portfolio.current_short),
        _format_portfolio_slot("Nearby long", portfolio.nearby_long),
        _format_portfolio_slot("Nearby short", portfolio.nearby_short),
    ]
    if portfolio.follow_up_opportunities:
        lines.append(
            "Follow-ups: "
            + ", ".join(
                (
                    f"{item.setup.direction.value.upper()} "
                    f"{item.setup.strategy.value} "
                    f"{item.setup.entry_status.value}"
                )
                for item in portfolio.follow_up_opportunities
            )
        )
    else:
        lines.append("Follow-ups: none")
    return tuple(lines)


def format_symbol_text(analysis: DiscoverySymbolAnalysis) -> str:
    """Format analysis with explicit routing, ranking, and canonical status."""

    base_text = _integrated.format_symbol_text(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    environment = getattr(analysis, "market_environment", None)
    portfolio = _opportunity_portfolio(analysis)
    primary = None if portfolio is None else portfolio.primary_opportunity
    setup = analysis.assessment.setup if primary is None else primary.setup
    decision = "NO_VALID_SETUP" if portfolio is None else portfolio.public_decision.value.upper()
    lines = [f"{analysis.symbol} | {decision}", base_text]
    if isinstance(route, MarketStrategyRoute):
        strategies = ", ".join(item.value for item in route.strategy_priority) or "none"
        environment_tradeable = "yes" if environment is not None and environment.tradeable else "no"
        lines.extend(
            (
                f"Environment tradeable: {environment_tradeable}",
                f"Strategy routed: {strategies}",
                f"Preferred direction: {route.preferred_direction.value}",
                f"Routing score: {route.routing_score:.1f}",
            )
        )
    candidate_diagnostics = analysis.phase5_diagnostics or {}
    lines.extend(_portfolio_summary_lines(analysis))
    lines.extend(_opportunity_summary_lines(analysis))
    lines.extend(
        (
            f"Raw candidates: {analysis.candidate_count}",
            "Candidate selection accepted: "
            f"{'yes' if candidate_diagnostics.get('selected') else 'no'}",
            f"Decision reason: {_decision_reason_code(analysis)}",
        )
    )
    if setup is not None:
        lines.extend(
            (
                f"Entry status: {setup.entry_status.value}",
                f"Strategy: {setup.strategy.value}",
                f"Confidence: {setup.confidence_score:.1f}",
            )
        )
    return "\n".join(lines)


def format_scan_text(result: DiscoveryScanResult) -> str:
    """Return decision-aware human-readable scanner output."""

    displayed = _display_analyses(result)
    lines = [
        f"Scan generated at {result.generated_at.isoformat()}",
        f"Showing top {len(displayed)} of {len(result.analyses)} analyzed symbols",
    ]
    lines.extend(format_symbol_text(analysis) for analysis in displayed)
    lines.extend(f"{symbol}: FAILED | {reason}" for symbol, reason in result.failures.items())
    return "\n".join(lines)


def _opportunity_summary_lines(
    analysis: DiscoverySymbolAnalysis,
) -> tuple[str, ...]:
    """Return compact operator-facing diagnostics for the best ranked candidate."""

    record = _best_rank_record(analysis)
    if record is None:
        ranking = analysis.candidate_ranking
        primary = None if ranking is None else ranking.primary
        if primary is not None and getattr(primary, "candidate_id", None) is None:
            record = primary
        elif ranking is not None:
            rejected = tuple(getattr(ranking, "rejected", ()))
            if len(rejected) == 1:
                only_rejected = next(iter(rejected))
                if getattr(only_rejected, "candidate_id", None) is None:
                    record = only_rejected

    if record is None:
        return ("Best opportunity: none",)

    dimensions = record.score_dimensions
    return (
        (
            f"Best opportunity: {record.quality_label.value.upper()} | "
            f"{record.strategy} {record.direction.upper()} | "
            f"rank score {record.final_rank_score:.1f}"
        ),
        (
            f"Score profile: opportunity {dimensions.opportunity_score:.1f} | "
            f"setup {dimensions.setup_score:.1f} | "
            f"timing {dimensions.timing_score:.1f} | "
            f"trade quality {dimensions.trade_quality_score:.1f} | "
            f"penalties {record.rank_penalty_score:.1f}"
        ),
    )


def _decision_reason_code(analysis: DiscoverySymbolAnalysis) -> str:
    gate = getattr(analysis, "methodology_gate", None)
    if isinstance(gate, Mapping) and gate.get("changed") is True:
        return "METHODOLOGY_SELECTED_STRATEGY_SUPPRESSED"
    environment = getattr(analysis, "market_environment", None)
    route = getattr(analysis, "market_strategy_route", None)
    candidate_diagnostics = analysis.phase5_diagnostics or {}
    if environment is not None and not environment.tradeable:
        return "ENVIRONMENT_BLOCKED"
    if route is not None and not route.strategy_priority:
        return "NO_ROUTED_STRATEGY"
    if analysis.candidate_count == 0:
        return "NO_CANDIDATE_GENERATED"
    portfolio = _opportunity_portfolio(analysis)
    if portfolio is not None and portfolio.opportunities:
        return portfolio.public_decision.value
    if not candidate_diagnostics.get("selected"):
        return "CANDIDATE_REJECTED"
    return PortfolioDecisionState.NO_VALID_SETUP.value


def _opportunity_portfolio(
    analysis: DiscoverySymbolAnalysis,
) -> SymbolOpportunityPortfolio | None:
    portfolio = getattr(analysis, "opportunity_portfolio", None)
    return portfolio if isinstance(portfolio, SymbolOpportunityPortfolio) else None


def _has_portfolio_opportunities(analysis: DiscoverySymbolAnalysis) -> bool:
    portfolio = _opportunity_portfolio(analysis)
    return portfolio is not None and bool(portfolio.opportunities)


def _portfolio_has_direction(
    analysis: DiscoverySymbolAnalysis,
    direction: str,
) -> bool:
    portfolio = _opportunity_portfolio(analysis)
    if portfolio is None:
        return False
    return any(item.direction.value == direction for item in portfolio.opportunities)


def _display_analyses(
    result: DiscoveryScanResult,
    *,
    limit: int = DEFAULT_SCAN_DISPLAY_LIMIT,
) -> tuple[SymbolAnalysis, ...]:
    """Return the default ranked display slice without mutating full scan results."""

    if limit < 1:
        raise ValueError("scan display limit must be positive")
    return cast(tuple[SymbolAnalysis, ...], result.analyses[:limit])


def _scan_sort_key(analysis: DiscoverySymbolAnalysis) -> tuple[int, float, int, str]:
    """Rank selected setups by execution maturity before raw Phase 5 quality."""

    record = _best_rank_record(analysis)
    maturity_class = _scan_maturity_class(analysis)
    if record is None:
        return (maturity_class, 0.0, 2**31 - 1, analysis.symbol)
    return (
        maturity_class,
        -record.final_rank_score,
        record.rank,
        analysis.symbol,
    )


def _scan_maturity_class(analysis: DiscoverySymbolAnalysis) -> int:
    """Return portfolio-aware actionable, developing, unavailable, or empty priority."""

    portfolio = getattr(analysis, "opportunity_portfolio", None)
    if portfolio is not None:
        if portfolio.current_long is not None or portfolio.current_short is not None:
            return 0
        if portfolio.nearby_long is not None or portfolio.nearby_short is not None:
            return 1
        if portfolio.follow_up_opportunities:
            maturities = tuple(
                derive_setup_maturity(
                    opportunity.setup.strategy,
                    opportunity.setup.entry_status,
                )
                for opportunity in portfolio.follow_up_opportunities
            )
            if any(item.execution_conditions_complete for item in maturities):
                return 0
            if any(item.maturity not in _UNAVAILABLE_MATURITIES for item in maturities):
                return 1
            return 2
        return 3

    assessment = analysis.assessment
    setup = assessment.setup or getattr(assessment, "developing_setup", None)
    if setup is None:
        return 3
    maturity = derive_setup_maturity(setup.strategy, setup.entry_status)
    if maturity.execution_conditions_complete:
        return 0
    if maturity.maturity in _UNAVAILABLE_MATURITIES:
        return 2
    return 1


def _best_rank_record(analysis: DiscoverySymbolAnalysis) -> Any | None:
    # Return the ranking record for the canonical retained opportunity.
    ranking = analysis.candidate_ranking
    if ranking is None:
        return None

    viable_records = (() if ranking.primary is None else (ranking.primary,)) + ranking.alternatives
    records_by_id = {
        item.candidate_id: item
        for item in viable_records
        if getattr(item, "candidate_id", None) is not None
    }
    if not records_by_id:
        return min(viable_records, key=lambda item: item.rank, default=None)

    portfolio = _opportunity_portfolio(analysis)
    if portfolio is not None:
        opportunities = getattr(
            portfolio,
            "opportunities",
            getattr(portfolio, "all_opportunities", ()),
        )
        for opportunity in opportunities:
            record = records_by_id.get(opportunity.opportunity_id)
            if record is not None:
                return record
        if records_by_id:
            return None

    return min(viable_records, key=lambda item: item.rank, default=None)
