"""Discovery-neutral analysis orchestration for live scan and analyze flows."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.application.discovery_context import (
    build_strategy_context,
    frame_data_quality_payload,
)
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.discovery_setup import build_discovery_assessment
from apex.application.futures_quality import analyze_futures_phase5
from apex.application.market_strategy_router import MarketStrategyRoute
from apex.application.methodology_candidate_routing import (
    evaluate_methodology_candidate_routing,
    methodology_candidate_routing_payload,
)
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.data.providers.base import MarketDataProvider
from apex.strategies import (
    analyze_strategies,
    strategy_evidence_payload,
    strategy_evidence_summary,
)


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
    market_strategy_route: MarketStrategyRoute | None = None,
    methodology_market_state: PrimaryMarketState | None = None,
    methodology_gate_mode: str = "shadow",
) -> SymbolAnalysis:
    """Run candidate discovery from market evidence and trade geometry."""

    if candle_limit < 40:
        raise ValueError("analysis requires at least 40 candles per timeframe")
    decision_time = generated_at or datetime.now(UTC)
    context, regimes = build_strategy_context(
        symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        received_at=decision_time,
    )
    strategy_analysis = analyze_strategies(context, decision_time=decision_time)
    routed = apply_strategy_routing(strategy_analysis, routing_config=strategy_routing)
    methodology_routing = evaluate_methodology_candidate_routing(
        routed,
        market_state=methodology_market_state,
        mode=methodology_gate_mode,
    )
    eligible_routed = methodology_routing.analysis
    selection = analyze_futures_phase5(
        eligible_routed,
        environment_route=market_strategy_route,
    )
    assessment = build_discovery_assessment(selection)
    ranking = build_candidate_ranking_snapshot(selection)
    return SymbolAnalysis(
        symbol=symbol,
        generated_at=decision_time,
        assessment=assessment,
        candidate_count=len(routed.candidates),
        evaluated_timeframes=tuple(frame.timeframe for frame in context.frames),
        regime_by_timeframe=regimes,
        data_quality_by_timeframe={
            frame.timeframe: {
                **frame_data_quality_payload(frame),
                "role": frame.role.value,
                "features": {
                    "atr": frame.features.atr,
                    "ema_fast": frame.features.ema_fast,
                    "ema_slow": frame.features.ema_slow,
                    "vwap": frame.features.vwap,
                    "rsi": frame.features.rsi,
                    "rsi_slope": frame.features.rsi_slope,
                    "stochastic": frame.features.stochastic,
                    "stochastic_rsi": frame.features.stochastic_rsi,
                    "macd_histogram": frame.features.macd_histogram,
                    "rate_of_change": frame.features.rate_of_change,
                    "relative_volume": frame.features.relative_volume,
                    "trend_strength": frame.features.trend_strength,
                    "range_position": frame.features.range_position,
                    "volatility_expansion": frame.features.volatility_expansion,
                },
            }
            for frame in context.frames
        },
        strategy_routing=dict(
            build_strategy_routing_payload(
                assessment=assessment,
                strategy_analysis=eligible_routed,
                routing_config=strategy_routing,
            )
        ),
        candidate_ranking=ranking,
        phase5_diagnostics={
            "candidate_count": len(selection.all_scored_candidates),
            "ranked_count": len(selection.ranked_candidates),
            "rejected_count": len(selection.rejected_candidates),
            "selected": selection.selected_candidate is not None,
            "selected_candidate_id": (
                selection.selected_candidate.scored.candidate_id
                if selection.selected_candidate is not None
                else None
            ),
            "no_trade_reason": selection.no_trade_reason,
            "methodology_candidate_routing": methodology_candidate_routing_payload(
                methodology_routing
            ),
            "candidates": [
                {
                    "candidate_id": item.scored.candidate_id,
                    "strategy": item.candidate.strategy.value,
                    "direction": item.candidate.direction.value,
                    "outcome": item.outcome.value,
                    "final_score": item.final_score,
                    "evidence": strategy_evidence_payload(item.candidate.evidence),
                    "evidence_summary": strategy_evidence_summary(item.candidate.evidence),
                    "metadata": dict(item.candidate.metadata),
                    "reasons": list(item.reasons),
                }
                for item in selection.ranked_candidates
            ],
        },
    )


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    **kwargs: Any,
) -> ScanResult:
    """Analyze symbols independently and rank usable discovery setups first."""

    timestamp = kwargs.pop("generated_at", None) or datetime.now(UTC)
    analyses: list[SymbolAnalysis] = []
    failures: dict[str, str] = {}
    for symbol in symbols:
        try:
            analyses.append(
                analyze_symbol(
                    symbol,
                    provider,
                    generated_at=timestamp,
                    **kwargs,
                )
            )
        except Exception as exc:  # Scanner intentionally isolates per-symbol failures.
            failures[symbol] = str(exc)
    return ScanResult(
        timestamp,
        tuple(sorted(analyses, key=_scan_sort_key)),
        failures,
    )


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Serialize discovery output without account-oriented fields."""

    setup = analysis.assessment.setup
    payload: dict[str, Any] = {
        "symbol": analysis.symbol,
        "generated_at": analysis.generated_at.isoformat(),
        "decision": setup.direction.value.upper() if setup is not None else "NO_TRADE",
        "entry_status": setup.entry_status.value if setup is not None else None,
        "strategy": setup.strategy.value if setup is not None else None,
        "confidence_score": setup.confidence_score if setup is not None else None,
        "reasons": list(analysis.assessment.reasons),
        "candidate_count": analysis.candidate_count,
        "evaluated_timeframes": list(analysis.evaluated_timeframes),
        "regime_by_timeframe": dict(analysis.regime_by_timeframe),
        "data_quality_by_timeframe": dict(analysis.data_quality_by_timeframe),
        "strategy_routing": analysis.strategy_routing,
        "phase5_diagnostics": analysis.phase5_diagnostics,
        "candidate_ranking": (
            candidate_ranking_payload(analysis.candidate_ranking)
            if analysis.candidate_ranking is not None
            else None
        ),
        "setup": None,
    }
    if setup is not None:
        payload["setup"] = {
            "candidate_id": setup.candidate_id,
            "direction": setup.direction.value,
            "strategy": setup.strategy.value,
            "entry_status": setup.entry_status.value,
            "confidence_score": setup.confidence_score,
            "entry": {
                "lower": setup.entry.lower,
                "upper": setup.entry.upper,
                "preferred": setup.entry.preferred,
                "current_price": setup.entry.current_price,
                "maximum_chase_price": setup.entry.maximum_chase_price,
                "current_price_inside_zone": setup.entry.current_price_inside_zone,
            },
            "stop_loss": {
                "price": setup.stop_loss.price,
                "distance": setup.stop_loss.distance,
                "distance_pct": setup.stop_loss.distance_pct,
                "quality_score": setup.stop_loss.quality_score,
                "quality_band": setup.stop_loss.quality_band.value,
                "rationale": list(setup.stop_loss.rationale),
            },
            "take_profits": [
                {
                    "label": target.label,
                    "price": target.price,
                    "reward": target.reward,
                    "risk_reward": target.risk_reward,
                    "partial_close_pct": target.partial_close_pct,
                    "rationale": list(target.rationale),
                }
                for target in setup.take_profits
            ],
            "management_policies": [
                {
                    "kind": policy.kind.value,
                    "trigger": policy.trigger,
                    "action": policy.action,
                    "rationale": list(policy.rationale),
                }
                for policy in setup.management_policies
            ],
            "warnings": list(setup.warnings),
        }
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    approved = result.approved
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "results": [serialize_symbol_analysis(item) for item in result.analyses],
        "failures": dict(result.failures),
    }


def format_symbol_text(analysis: SymbolAnalysis) -> str:
    setup = analysis.assessment.setup
    if setup is None:
        return (
            f"{analysis.symbol} | NO_TRADE | "
            f"{'; '.join(analysis.assessment.reasons)}"
        )
    targets = ", ".join(
        f"{target.label} {target.price:.8g} ({target.risk_reward:.2f}R)"
        for target in setup.take_profits
    )
    return "\n".join(
        (
            f"{analysis.symbol} | {setup.direction.value.upper()} | "
            f"{setup.strategy.value} | {setup.entry_status.value}",
            f"Score: {setup.confidence_score:.1f}",
            f"Entry: {setup.entry.lower:.8g}-{setup.entry.upper:.8g} | "
            f"preferred {setup.entry.preferred:.8g}",
            f"Stop: {setup.stop_loss.price:.8g} "
            f"({setup.stop_loss.distance_pct:.2f}%)",
            f"Targets: {targets}",
        )
    )


def format_scan_text(result: ScanResult) -> str:
    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    lines.extend(format_symbol_text(item) for item in result.analyses)
    lines.extend(
        f"{symbol}: FAILED | {reason}"
        for symbol, reason in result.failures.items()
    )
    return "\n".join(lines)


def write_json_report(payload: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _scan_sort_key(
    analysis: SymbolAnalysis,
) -> tuple[int, float, float, str]:
    setup = analysis.assessment.setup
    if setup is None:
        return (1, 0.0, 0.0, analysis.symbol)
    best_rr = max(target.risk_reward for target in setup.take_profits)
    return (0, -setup.confidence_score, -best_rr, analysis.symbol)
