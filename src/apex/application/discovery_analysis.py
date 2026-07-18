"""Discovery-neutral analysis orchestration for live scan and analyze flows."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.application.candlestick_evidence import (
    candlestick_evidence_observations,
    candlestick_evidence_payload,
    detect_contextual_candlesticks,
)
from apex.application.discovery_context import (
    build_strategy_context,
    frame_data_quality_payload,
)
from apex.application.discovery_contracts import (
    DiscoverySetup,
    ScanResult,
    SymbolAnalysis,
    TakeProfit,
)
from apex.application.discovery_setup import build_discovery_assessment
from apex.application.futures_quality import analyze_futures_phase5
from apex.application.market_strategy_router import MarketStrategyRoute
from apex.application.methodology_candidate_routing import (
    evaluate_methodology_candidate_routing,
    methodology_candidate_routing_payload,
)
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    ConfidenceBasis,
    ConfidenceLabel,
    DurationExpectation,
    EntryOpportunity,
    EntryOpportunityType,
    HoldCategory,
    InvalidationRule,
    RejectionCode,
    RejectionReason,
    RejectionSeverity,
    StructuralInvalidation,
    TargetCandidate,
    TargetRole,
)
from apex.application.methodology_phase5_evidence import (
    selected_candidate_methodology_evidence,
)
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_setup_maturity import derive_setup_maturity
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.data.providers.base import MarketDataProvider
from apex.strategies import (
    StrategyContext,
    analyze_strategies,
    strategy_evidence_payload,
    strategy_evidence_summary,
)
from apex.strategies.entry_status import EntryStatus


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
    candlestick_patterns = detect_contextual_candlesticks(context)
    candlestick_observations = candlestick_evidence_observations(candlestick_patterns)
    phase5_diagnostics = {
        "candidate_count": len(selection.all_scored_candidates),
        "raw_candidate_count": len(strategy_analysis.candidates),
        "retained_candidate_count": len(eligible_routed.candidates),
        "ranked_count": len(selection.ranked_candidates),
        "rejected_count": len(selection.rejected_candidates),
        "selected": selection.selected_candidate is not None,
        "developing_setup_selected": assessment.developing_setup is not None,
        "selected_candidate_id": (
            selection.selected_candidate.scored.candidate_id
            if selection.selected_candidate is not None
            else None
        ),
        "no_trade_reason": selection.no_trade_reason,
        "zero_trade_diagnostics": _zero_trade_diagnostics(
            strategy_analysis=strategy_analysis,
            eligible_routed=eligible_routed,
            selection=selection,
            assessment=assessment,
            methodology_routing=methodology_routing,
        ),
        "methodology_candidate_routing": methodology_candidate_routing_payload(methodology_routing),
        "candlestick_evidence": candlestick_evidence_payload(candlestick_patterns),
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
    }
    selected_candidate_id = None if assessment.setup is None else assessment.setup.candidate_id
    phase5_observations, contradictions = (
        ((), ())
        if selected_candidate_id is None
        else selected_candidate_methodology_evidence(
            phase5_diagnostics,
            candidate_id=selected_candidate_id,
        )
    )
    methodology = _build_native_methodology_snapshot(
        assessment.setup,
        context=context,
        evidence=tuple((*phase5_observations, *candlestick_observations)),
        contradictions=contradictions,
        no_trade_reason=selection.no_trade_reason,
    )
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
        phase5_diagnostics=phase5_diagnostics,
        methodology=methodology,
    )


def _zero_trade_diagnostics(
    *,
    strategy_analysis: Any,
    eligible_routed: Any,
    selection: Any,
    assessment: Any,
    methodology_routing: Any,
) -> dict[str, Any]:
    """Summarize why a decision did or did not become an executable setup."""

    raw_status_counts = Counter(
        item.status.value for item in getattr(strategy_analysis, "candidate_actionability", ())
    )
    retained_status_counts = Counter(
        item.status.value for item in getattr(eligible_routed, "candidate_actionability", ())
    )
    family_counts = Counter(
        item.strategy.canonical_family.value for item in getattr(eligible_routed, "candidates", ())
    )
    strategy_diagnostics = getattr(strategy_analysis, "strategy_diagnostics", None) or {}
    rejection_codes = Counter(
        code.value
        for diagnostic in strategy_diagnostics.values()
        for code in diagnostic.rejection_codes
    )
    strategy_summary = {
        strategy.value: {
            "candidate_count": diagnostic.candidate_count,
            "canonical_family": strategy.canonical_family.value,
            "canonical_subtype": strategy.canonical_subtype,
            "near_miss_state": diagnostic.near_miss_state.value,
            "rejection_codes": [code.value for code in diagnostic.rejection_codes],
            "reasons": list(diagnostic.reasons),
        }
        for strategy, diagnostic in strategy_diagnostics.items()
    }
    ranked_outcomes = Counter(item.outcome.value for item in selection.ranked_candidates)
    rejected_reasons = Counter(
        reason for item in selection.rejected_candidates for reason in item.reasons
    )
    selected = selection.selected_candidate
    developing = assessment.developing_setup
    return {
        "diagnostic_version": 1,
        "execution_filter_policy": (
            "strict: diagnostics may explain zero trades, but do not loosen entry filters"
        ),
        "decision": "TRADE" if selected is not None else "NO_TRADE",
        "no_trade_reason": selection.no_trade_reason,
        "selection_summary": {
            "raw_candidate_count": len(strategy_analysis.candidates),
            "retained_candidate_count": len(eligible_routed.candidates),
            "ranked_count": len(selection.ranked_candidates),
            "rejected_count": len(selection.rejected_candidates),
            "selected_candidate_id": None if selected is None else selected.scored.candidate_id,
            "developing_candidate_id": None if developing is None else developing.candidate_id,
        },
        "entry_status_distribution": {
            "raw": dict(sorted(raw_status_counts.items())),
            "retained": dict(sorted(retained_status_counts.items())),
        },
        "canonical_family_distribution": dict(sorted(family_counts.items())),
        "ranked_outcome_distribution": dict(sorted(ranked_outcomes.items())),
        "strategy_rejection_code_distribution": dict(sorted(rejection_codes.items())),
        "top_rejected_reasons": [
            {"reason": reason, "count": count} for reason, count in rejected_reasons.most_common(8)
        ],
        "strategy_diagnostics": strategy_summary,
        "methodology_shadow_vs_enforce": {
            "mode": methodology_routing.mode.value,
            "suppressed_candidate_count": methodology_routing.suppressed_candidate_count,
            "suppressed_strategies": [
                strategy.value for strategy in methodology_routing.suppressed_strategies
            ],
            "reason_codes": list(methodology_routing.reason_codes),
        },
    }


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
        "strategy_family": setup.strategy.canonical_family.value if setup is not None else None,
        "strategy_subtype": setup.strategy.canonical_subtype if setup is not None else None,
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
        "developing_setup": None,
    }
    if setup is not None:
        payload["setup"] = _setup_payload(setup)
    developing_setup = analysis.assessment.developing_setup
    if developing_setup is not None:
        payload["developing_setup"] = _setup_payload(developing_setup)
    return payload


def _setup_payload(setup: DiscoverySetup) -> dict[str, Any]:
    return {
        "candidate_id": setup.candidate_id,
        "direction": setup.direction.value,
        "strategy": setup.strategy.value,
        "strategy_family": setup.strategy.canonical_family.value,
        "strategy_subtype": setup.strategy.canonical_subtype,
        "entry_status": setup.entry_status.value,
        "confidence_score": setup.confidence_score,
        "trader_headline": setup.trader_headline,
        "execution_allowed_now": setup.execution_allowed_now,
        "setup_expiry_seconds": setup.setup_expiry_seconds,
        "setup_expiry_bars": setup.setup_expiry_bars,
        "setup_validity": _duration_label(setup.setup_expiry_seconds),
        "setup_expiry_reason": setup.setup_expiry_reason,
        "quality_dimensions": (
            None
            if setup.quality_dimensions is None
            else {
                "setup_quality": setup.quality_dimensions.setup_quality,
                "execution_quality": setup.quality_dimensions.execution_quality,
                "target_quality": setup.quality_dimensions.target_quality,
                "risk_quality": setup.quality_dimensions.risk_quality,
                "overall_trade_quality": setup.quality_dimensions.overall_trade_quality,
            }
        ),
        "entry": {
            "lower": setup.entry.lower,
            "upper": setup.entry.upper,
            "preferred": setup.entry.preferred,
            "current_price": setup.entry.current_price,
            "maximum_chase_price": setup.entry.maximum_chase_price,
            "current_price_inside_zone": setup.entry.current_price_inside_zone,
        },
        "alternative_entry_opportunities": [
            {
                "lower": opportunity.lower,
                "upper": opportunity.upper,
                "preferred": opportunity.preferred,
                "current_price": opportunity.current_price,
                "maximum_chase_price": opportunity.maximum_chase_price,
                "current_price_inside_zone": opportunity.current_price_inside_zone,
            }
            for opportunity in setup.entry_opportunities
            if opportunity != setup.entry
        ],
        "stop_loss": {
            "price": setup.stop_loss.price,
            "distance": setup.stop_loss.distance,
            "distance_pct": setup.stop_loss.distance_pct,
            "quality_score": setup.stop_loss.quality_score,
            "quality_band": setup.stop_loss.quality_band.value,
            "stop_type": setup.stop_loss.invalidation_type.value,
            "single_buffer_rationale": setup.stop_loss.buffer_rationale,
            "rationale": list(setup.stop_loss.rationale),
            "quality_evidence": _stop_quality_evidence(setup),
        },
        "take_profits": [
            {
                "label": target.label,
                "price": target.price,
                "reward": target.reward,
                "risk_reward": target.risk_reward,
                "partial_close_pct": target.partial_close_pct,
                "target_type": target.target_type.value,
                "purpose": target.purpose,
                "context": _target_context(setup, target),
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


def _stop_quality_evidence(setup: DiscoverySetup) -> dict[str, Any]:
    risk = setup.stop_loss.distance
    entry = setup.entry.preferred
    return {
        "strategy_family": setup.strategy.canonical_family.value,
        "structural_significance": setup.stop_loss.invalidation_type.value,
        "noise_clearance": setup.stop_loss.buffer_rationale,
        "distance_pct": setup.stop_loss.distance_pct,
        "risk_unit": risk,
        "cost_adjusted_r_note": (
            "execution costs are not deducted here; use backtest calibration records"
        ),
        "close_or_touch_rule": "close",
        "distance_from_entry": abs(entry - setup.stop_loss.price),
    }


def _target_context(setup: DiscoverySetup, target: TakeProfit) -> dict[str, Any]:
    expected_move_pct = abs(target.price - setup.entry.preferred) / setup.entry.preferred * 100.0
    return {
        "strategy_family": setup.strategy.canonical_family.value,
        "source": target.target_type.value,
        "role": target.purpose,
        "expected_move_pct": expected_move_pct,
        "risk_multiple": target.risk_reward,
        "conditional": target.target_type.value == "expansion",
        "reachable_within_setup_life": (
            None if setup.setup_expiry_seconds is None else target.risk_reward <= 3.0
        ),
    }


def _duration_label(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    minutes, remaining = divmod(seconds, 60)
    if remaining == 0:
        return f"{minutes} minutes"
    return f"{minutes}m {remaining}s"


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
        return f"{analysis.symbol} | NO_TRADE | {'; '.join(analysis.assessment.reasons)}"
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
            f"Stop: {setup.stop_loss.price:.8g} ({setup.stop_loss.distance_pct:.2f}%)",
            f"Targets: {targets}",
        )
    )


def format_scan_text(result: ScanResult) -> str:
    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    lines.extend(format_symbol_text(item) for item in result.analyses)
    lines.extend(f"{symbol}: FAILED | {reason}" for symbol, reason in result.failures.items())
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


def _build_native_methodology_snapshot(
    setup: DiscoverySetup | None,
    *,
    context: StrategyContext,
    evidence: tuple[Any, ...],
    contradictions: tuple[Any, ...],
    no_trade_reason: str | None,
) -> MethodologySnapshot:
    if setup is None:
        return MethodologySnapshot(
            evidence=evidence,
            contradictions=contradictions,
            rejections=(_no_trade_rejection(no_trade_reason),),
        )

    maturity = derive_setup_maturity(setup.strategy, setup.entry_status)
    entry_opportunity = _entry_opportunity(setup, context)
    selected_entry = SelectedEntryDecision(
        opportunity=entry_opportunity,
        reason="selected setup entry geometry passed Phase 5 candidate selection",
    )
    invalidation = StructuralInvalidation(
        price=setup.stop_loss.price,
        rule=InvalidationRule.CLOSE,
        structure="; ".join(setup.stop_loss.rationale),
        failure_event=f"{setup.strategy.value} thesis fails at the structural stop",
        volatility_buffer=max(
            0.0,
            setup.stop_loss.distance - abs(setup.entry.preferred - setup.stop_loss.price),
        ),
        estimated_slippage=0.0,
    )
    targets = tuple(
        TargetCandidate(
            role=_target_role(index, len(setup.take_profits)),
            price=target.price,
            source="; ".join(target.rationale),
            expected_move_percentage=abs(target.price - setup.entry.preferred)
            / setup.entry.preferred
            * 100.0,
            risk_multiple=target.risk_reward,
            conditional=index > 3,
        )
        for index, target in enumerate(setup.take_profits, start=1)
    )
    confidence = ConfidenceAssessment(
        setup=_confidence_label(setup.confidence_score),
        execution=_confidence_label(entry_opportunity.quality * 100.0),
        target=_confidence_label(max(target.risk_reward for target in setup.take_profits) * 25.0),
        data=ConfidenceLabel.HIGH
        if all(not frame.is_stale for frame in context.frames)
        else ConfidenceLabel.LOW,
        historical=ConfidenceLabel.VERY_LOW,
        overall=_confidence_label(setup.confidence_score),
        basis=ConfidenceBasis.RULE_BASED,
        strongest_support=_strongest_support(evidence, setup),
        strongest_contradiction=(
            None if not contradictions else str(getattr(contradictions[0], "reason", ""))
        ),
        missing_evidence=(
            "historical calibration",
            "out-of-sample probability",
            "execution cost provenance",
        ),
    )
    return MethodologySnapshot(
        direction=setup.direction,
        setup_maturity=maturity.maturity,
        confirmation_policy=maturity.confirmation_policy,
        evidence=evidence,
        contradictions=contradictions,
        entry_opportunities=(entry_opportunity,),
        selected_entry=selected_entry,
        invalidation=invalidation,
        targets=targets,
        duration=_duration_expectation(context),
        confidence=confidence,
        rejections=_soft_rejections(setup),
    )


def _entry_opportunity(
    setup: DiscoverySetup,
    context: StrategyContext,
) -> EntryOpportunity:
    current = setup.entry.current_price
    if setup.entry.lower <= current <= setup.entry.upper:
        distance = 0.0
    else:
        distance = min(abs(current - setup.entry.lower), abs(current - setup.entry.upper))
    return EntryOpportunity(
        kind=_entry_kind(setup.entry_status),
        zone_low=setup.entry.lower,
        zone_high=setup.entry.upper,
        ideal_entry=setup.entry.preferred,
        confirmation_level=_confirmation_level(setup),
        maximum_chase=setup.entry.maximum_chase_price,
        current_distance_percentage=distance / current * 100.0,
        current_distance_atr=distance / context.atr,
        quality=_entry_quality(setup.entry_status),
        reason=(
            f"{setup.entry_status.value} entry derived from selected {setup.strategy.value} setup"
        ),
        expiry_bars=_expiry_bars(setup.entry_status),
    )


def _entry_kind(status: EntryStatus) -> EntryOpportunityType:
    if status is EntryStatus.READY_NOW:
        return EntryOpportunityType.IMMEDIATE
    if status is EntryStatus.AGGRESSIVE_NOW:
        return EntryOpportunityType.AGGRESSIVE
    if status is EntryStatus.PULLBACK_PREFERRED:
        return EntryOpportunityType.PULLBACK
    if status is EntryStatus.WATCH_NEAR_ENTRY:
        return EntryOpportunityType.DEVELOPING_FUTURE
    if status is EntryStatus.LATE_OR_CHASING:
        return EntryOpportunityType.RETEST
    return EntryOpportunityType.DEVELOPING_FUTURE


def _entry_quality(status: EntryStatus) -> float:
    return {
        EntryStatus.READY_NOW: 0.9,
        EntryStatus.AGGRESSIVE_NOW: 0.75,
        EntryStatus.PULLBACK_PREFERRED: 0.7,
        EntryStatus.WATCH_NEAR_ENTRY: 0.55,
        EntryStatus.LATE_OR_CHASING: 0.25,
        EntryStatus.INVALIDATED: 0.05,
    }[status]


def _confirmation_level(setup: DiscoverySetup) -> float | None:
    if setup.entry_status is EntryStatus.READY_NOW:
        return None
    return setup.entry.upper if setup.direction.value == "long" else setup.entry.lower


def _expiry_bars(status: EntryStatus) -> int:
    if status in {EntryStatus.READY_NOW, EntryStatus.AGGRESSIVE_NOW}:
        return 3
    if status is EntryStatus.PULLBACK_PREFERRED:
        return 8
    if status is EntryStatus.WATCH_NEAR_ENTRY:
        return 12
    return 2


def _duration_expectation(context: StrategyContext) -> DurationExpectation:
    seconds = _timeframe_seconds(context.decision_frame.timeframe)
    expected_bars = 12
    expiry_bars = 8
    return DurationExpectation(
        category=_hold_category(seconds),
        expected_hold_min_seconds=max(seconds, seconds * 3),
        expected_hold_max_seconds=seconds * expected_bars,
        expected_bars=expected_bars,
        setup_expiry_bars=expiry_bars,
        expiry_reason="derived from selected setup timeframe and methodology expiry policy",
    )


def _timeframe_seconds(timeframe: str) -> int:
    unit = timeframe[-1].lower()
    value = int(timeframe[:-1])
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 60 * 60
    if unit == "d":
        return value * 24 * 60 * 60
    if unit == "w":
        return value * 7 * 24 * 60 * 60
    return 15 * 60


def _hold_category(seconds: int) -> HoldCategory:
    if seconds <= 60:
        return HoldCategory.MICRO_SCALP
    if seconds <= 5 * 60:
        return HoldCategory.SCALP
    if seconds <= 60 * 60:
        return HoldCategory.INTRADAY
    if seconds <= 4 * 60 * 60:
        return HoldCategory.MULTI_SESSION
    return HoldCategory.SWING


def _target_role(index: int, count: int) -> TargetRole:
    if index == 1:
        return TargetRole.TP1
    if index == 2:
        return TargetRole.TP2
    if index == 3 and count == 3:
        return TargetRole.TP3
    return TargetRole.RUNNER


def _confidence_label(score: float) -> ConfidenceLabel:
    if score >= 85:
        return ConfidenceLabel.VERY_HIGH
    if score >= 70:
        return ConfidenceLabel.HIGH
    if score >= 55:
        return ConfidenceLabel.MODERATE
    if score >= 35:
        return ConfidenceLabel.LOW
    return ConfidenceLabel.VERY_LOW


def _strongest_support(evidence: tuple[Any, ...], setup: DiscoverySetup) -> str:
    for item in evidence:
        reason = getattr(item, "reason", "")
        effect = getattr(item, "effect", None)
        if reason and getattr(effect, "value", None) == "supports":
            return str(reason)
    return f"{setup.strategy.value} selected with rule-based score {setup.confidence_score:.1f}"


def _soft_rejections(setup: DiscoverySetup) -> tuple[RejectionReason, ...]:
    if setup.entry_status not in {EntryStatus.LATE_OR_CHASING, EntryStatus.INVALIDATED}:
        return ()
    code = (
        RejectionCode.CLEARLY_MISSED_ENTRY
        if setup.entry_status is EntryStatus.LATE_OR_CHASING
        else RejectionCode.STRUCTURALLY_INVALIDATED
    )
    severity = (
        RejectionSeverity.SOFT_PENALTY
        if setup.entry_status is EntryStatus.LATE_OR_CHASING
        else RejectionSeverity.HARD_BLOCKER
    )
    return (
        RejectionReason(
            code=code,
            severity=severity,
            reason=f"selected setup status is {setup.entry_status.value}",
            penalty=0.25 if severity is RejectionSeverity.SOFT_PENALTY else 0.0,
        ),
    )


def _no_trade_rejection(reason: str | None) -> RejectionReason:
    text = reason or "candidate selection produced no setup"
    normalized = text.lower()
    if "target" in normalized:
        code = RejectionCode.NO_REALISTIC_TARGET_ROOM
    elif "invalid" in normalized:
        code = RejectionCode.STRUCTURALLY_INVALIDATED
    elif "entry" in normalized and "miss" in normalized:
        code = RejectionCode.CLEARLY_MISSED_ENTRY
    else:
        code = RejectionCode.WRONG_STRATEGY_FOR_STATE
    return RejectionReason(
        code=code,
        severity=RejectionSeverity.HARD_BLOCKER,
        reason=text,
    )
