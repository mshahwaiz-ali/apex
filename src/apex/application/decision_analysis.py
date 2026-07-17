"""Canonical strategy-routing analysis orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.application import integrated_analysis as _integrated
from apex.application.discovery_contracts import ScanResult
from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    market_strategy_route_payload,
    route_market_strategies,
)
from apex.data.providers.base import MarketDataProvider
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig

DEFAULT_SCAN_DISPLAY_LIMIT = 15


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
    candle_limit: int = 200,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> SymbolAnalysis:
    """Run integrated discovery analysis and attach canonical market routing."""

    base = _integrated.analyze_symbol(
        symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit + 1,
        generated_at=generated_at,
        strategy_routing=strategy_routing,
        market_environment_config=market_environment_config,
    )
    environment = base.market_environment
    route = route_market_strategies(environment) if environment is not None else None
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
        market_environment=environment,
        market_state=base.market_state,
        market_strategy_route=route,
    )


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_environment_config: MarketEnvironmentConfig = DEFAULT_MARKET_ENVIRONMENT_CONFIG,
) -> ScanResult:
    """Analyze each symbol once with canonical routing and ranking."""

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


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Serialize one analysis with canonical strategy routing."""

    payload = _integrated.serialize_symbol_analysis(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    payload["market_strategy_route"] = (
        market_strategy_route_payload(route) if isinstance(route, MarketStrategyRoute) else None
    )
    payload["decision_reason_code"] = _decision_reason_code(analysis)
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    """Return scanner JSON with decision-aware nested analyses."""

    displayed = _display_analyses(result)
    approved = tuple(item for item in displayed if item.assessment.setup is not None)
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
        "results": [serialize_symbol_analysis(item) for item in displayed],
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(displayed),
        "display_limit": DEFAULT_SCAN_DISPLAY_LIMIT,
        "failures": dict(result.failures),
    }


def format_symbol_text(analysis: SymbolAnalysis) -> str:
    """Format analysis with explicit routing, ranking, and canonical status."""

    base_text = _integrated.format_symbol_text(analysis)
    route = getattr(analysis, "market_strategy_route", None)
    environment = getattr(analysis, "market_environment", None)
    setup = analysis.assessment.setup
    decision = "NO_TRADE" if setup is None else setup.direction.value.upper()
    lines = [f"{analysis.symbol} | {decision}", base_text]
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
    candidate_diagnostics = analysis.phase5_diagnostics or {}
    lines.extend(_opportunity_summary_lines(analysis))
    lines.extend(
        (
            f"Raw candidates: {analysis.candidate_count}",
            f"Candidate selection accepted: {'yes' if candidate_diagnostics.get('selected') else 'no'}",
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


def format_scan_text(result: ScanResult) -> str:
    """Return decision-aware human-readable scanner output."""

    displayed = _display_analyses(result)
    lines = [
        f"Scan generated at {result.generated_at.isoformat()}",
        f"Showing top {len(displayed)} of {len(result.analyses)} analyzed symbols",
    ]
    lines.extend(format_symbol_text(analysis) for analysis in displayed)
    lines.extend(f"{symbol}: FAILED | {reason}" for symbol, reason in result.failures.items())
    return "\n".join(lines)


def _opportunity_summary_lines(analysis: SymbolAnalysis) -> tuple[str, ...]:
    """Return compact operator-facing diagnostics for the best ranked candidate."""

    record = _best_rank_record(analysis)
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


def _decision_reason_code(analysis: SymbolAnalysis) -> str:
    environment = getattr(analysis, "market_environment", None)
    route = getattr(analysis, "market_strategy_route", None)
    candidate_diagnostics = analysis.phase5_diagnostics or {}
    if environment is not None and not environment.tradeable:
        return "ENVIRONMENT_BLOCKED"
    if route is not None and not route.strategy_priority:
        return "NO_ROUTED_STRATEGY"
    if analysis.candidate_count == 0:
        return "NO_CANDIDATE_GENERATED"
    if not candidate_diagnostics.get("selected"):
        return "CANDIDATE_REJECTED"
    setup = analysis.assessment.setup
    return "NO_TRADE" if setup is None else setup.entry_status.value


def _display_analyses(
    result: ScanResult,
    *,
    limit: int = DEFAULT_SCAN_DISPLAY_LIMIT,
) -> tuple[SymbolAnalysis, ...]:
    """Return the default ranked display slice without mutating full scan results."""

    if limit < 1:
        raise ValueError("scan display limit must be positive")
    return result.analyses[:limit]


def _scan_sort_key(analysis: SymbolAnalysis) -> tuple[float, int, str]:
    record = _best_rank_record(analysis)
    if record is None:
        return (0.0, 1, analysis.symbol)
    return (
        -record.final_rank_score,
        0 if analysis.assessment.setup is not None else 1,
        analysis.symbol,
    )


def _best_rank_record(analysis: SymbolAnalysis) -> Any | None:
    ranking = analysis.candidate_ranking
    if ranking is None:
        return None
    records = (
        (() if ranking.primary is None else (ranking.primary,))
        + ranking.alternatives
        + ranking.rejected
    )
    return min(records, key=lambda item: item.rank, default=None)
