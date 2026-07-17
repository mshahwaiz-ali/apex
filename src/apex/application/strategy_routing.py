"""Deterministic strategy-routing metadata for scanner and analysis output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.config import DEFAULT_STRATEGY_ROUTING
from apex.strategies import (
    StrategyAnalysisResult,
    StrategyType,
    SuppressedStrategyCandidate,
    TradeCandidate,
    strategy_evidence_payload,
    strategy_evidence_summary,
)


def apply_strategy_routing(
    strategy_analysis: StrategyAnalysisResult,
    *,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> StrategyAnalysisResult:
    """Filter candidates through the canonical enabled-strategy configuration."""

    configured = _normalize_routing_config(routing_config)
    eligible = tuple(
        strategy
        for strategy in strategy_analysis.eligible_strategies or ()
        if strategy in configured
    )
    skipped = dict(strategy_analysis.skipped_strategies or {})
    for strategy in strategy_analysis.evaluated_strategies:
        if strategy not in configured:
            skipped.setdefault(
                strategy,
                f"{strategy.value} is disabled by configured strategy routing",
            )
    candidates = tuple(
        candidate
        for candidate in strategy_analysis.candidates
        if candidate.strategy in eligible
    )
    newly_suppressed = tuple(
        SuppressedStrategyCandidate(
            candidate=candidate,
            reason_codes=("STRATEGY_DISABLED_BY_CONFIG",),
            reasons=(
                f"{candidate.strategy.value} is disabled by configured "
                "strategy routing",
            ),
        )
        for candidate in strategy_analysis.candidates
        if candidate.strategy not in configured
    )
    suppressed_candidates = strategy_analysis.suppressed_candidates + newly_suppressed
    return StrategyAnalysisResult(
        symbol=strategy_analysis.symbol,
        decision_time=strategy_analysis.decision_time,
        candidates=candidates,
        evaluated_strategies=strategy_analysis.evaluated_strategies,
        eligible_strategies=eligible,
        skipped_strategies=skipped,
        strategy_diagnostics=strategy_analysis.strategy_diagnostics,
        decision_regime=strategy_analysis.decision_regime,
        higher_timeframe_breakout=strategy_analysis.higher_timeframe_breakout,
        strategy_applicability=strategy_analysis.strategy_applicability,
        suppressed_candidates=suppressed_candidates,
    )


def build_strategy_routing_payload(
    *,
    assessment: DiscoveryAssessment,
    strategy_analysis: StrategyAnalysisResult | None = None,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Return reproducible routing metadata without category-specific paths."""

    enabled = _normalize_routing_config(routing_config)
    disabled = tuple(strategy for strategy in StrategyType if strategy not in enabled)
    setup = assessment.setup
    selected_strategy = setup.strategy if setup is not None else None
    selected_strategy_enabled = (
        selected_strategy in enabled if selected_strategy is not None else False
    )
    routed_eligible = (
        tuple(strategy_analysis.eligible_strategies or ())
        if strategy_analysis is not None
        else ()
    )
    selected_strategy_routed_eligible = (
        selected_strategy in routed_eligible if selected_strategy is not None else False
    )
    reasons = ["canonical strategy routing applied"]
    if strategy_analysis is not None:
        reasons.append(
            f"decision regime {strategy_analysis.decision_regime.value} applied to routing"
        )
        if strategy_analysis.higher_timeframe_breakout:
            reasons.append("higher-timeframe breakout continuation routing was active")
    diagnostics = (
        {
            strategy.value: {
                "candidate_count": diagnostic.candidate_count,
                "rejection_codes": [code.value for code in diagnostic.rejection_codes],
                "reasons": list(diagnostic.reasons),
                "near_miss_state": diagnostic.near_miss_state.value,
                "higher_timeframe_breakout": diagnostic.higher_timeframe_breakout,
            }
            for strategy, diagnostic in strategy_analysis.strategy_diagnostics.items()
        }
        if strategy_analysis is not None
        and strategy_analysis.strategy_diagnostics is not None
        else {}
    )
    near_miss_counts: dict[str, int] = {}
    for diagnostic in diagnostics.values():
        state = str(diagnostic["near_miss_state"])
        near_miss_counts[state] = near_miss_counts.get(state, 0) + 1
    return {
        "enabled_strategies": [
            strategy.value for strategy in sorted(enabled, key=lambda item: item.value)
        ],
        "disabled_strategies": [strategy.value for strategy in disabled],
        "selected_strategy": selected_strategy.value if selected_strategy is not None else None,
        "selected_strategy_enabled": selected_strategy_enabled,
        "selected_strategy_routed_eligible": selected_strategy_routed_eligible,
        "decision_regime": (
            strategy_analysis.decision_regime.value
            if strategy_analysis is not None
            else None
        ),
        "higher_timeframe_breakout": (
            strategy_analysis.higher_timeframe_breakout
            if strategy_analysis is not None
            else False
        ),
        "routed_eligible_strategies": [strategy.value for strategy in routed_eligible],
        "skipped_strategies": (
            {
                strategy.value: reason
                for strategy, reason in strategy_analysis.skipped_strategies.items()
            }
            if strategy_analysis is not None
            and strategy_analysis.skipped_strategies is not None
            else {}
        ),
        "phase4_strategy_diagnostics": diagnostics,
        "strategy_applicability": _strategy_applicability_payload(strategy_analysis),
        "suppressed_candidates": _suppressed_candidate_payload(strategy_analysis),
        "candidate_diagnostics": _candidate_diagnostics(strategy_analysis),
        "near_miss_state_counts": near_miss_counts,
        "eligible": setup is not None,
        "reasons": reasons,
        "rejections": list(assessment.reasons),
    }


def _strategy_applicability_payload(
    strategy_analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if strategy_analysis is None:
        return []
    applicability = strategy_analysis.strategy_applicability or {}
    records: list[dict[str, object]] = []
    eligible = tuple(strategy_analysis.eligible_strategies or ())
    for strategy in strategy_analysis.evaluated_strategies:
        record = applicability.get(strategy)
        if record is None:
            continue
        records.append(
            {
                "strategy": strategy.value,
                "state": record.state.value,
                "score": record.score,
                "reason_codes": list(record.reason_codes),
                "reasons": list(record.reasons),
                "enabled": strategy in eligible,
            }
        )
    return records


def _suppressed_candidate_payload(
    strategy_analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if strategy_analysis is None:
        return []
    return [
        {
            **_generated_candidate_payload(item.candidate),
            "routing_status": "suppressed",
            "reason_codes": list(item.reason_codes),
            "reasons": list(item.reasons),
        }
        for item in strategy_analysis.suppressed_candidates
    ]


def _candidate_diagnostics(
    strategy_analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if strategy_analysis is None:
        return []
    diagnostics = strategy_analysis.strategy_diagnostics or {}
    records: list[dict[str, object]] = []
    for strategy in strategy_analysis.evaluated_strategies:
        strategy_candidates = tuple(
            candidate
            for candidate in strategy_analysis.candidates
            if candidate.strategy is strategy
        )
        diagnostic = diagnostics.get(strategy)
        if strategy_candidates:
            records.extend(
                _generated_candidate_payload(candidate)
                for candidate in strategy_candidates
            )
            continue
        records.append(
            {
                "strategy": strategy.value,
                "direction": None,
                "generated": False,
                "candidate_score": None,
                "entry_zone_low": None,
                "entry_zone_high": None,
                "ideal_entry": None,
                "maximum_chase_price": None,
                "current_price": None,
                "entry_quality": None,
                "chase_classification": None,
                "accepted": False,
                "rejected": True,
                "rejection_codes": (
                    [code.value for code in diagnostic.rejection_codes]
                    if diagnostic is not None
                    else []
                ),
                "rejection_reasons": (
                    list(diagnostic.reasons) if diagnostic is not None else []
                ),
                "nearest_future_trigger": None,
                "near_miss_state": (
                    diagnostic.near_miss_state.value
                    if diagnostic is not None
                    else None
                ),
                "invalidation": None,
            }
        )
    return records


def _generated_candidate_payload(candidate: TradeCandidate) -> dict[str, object]:
    metadata = candidate.metadata
    return {
        "strategy": candidate.strategy.value,
        "direction": candidate.direction.value,
        "generated": True,
        "candidate_score": None,
        "entry_zone_low": candidate.entry.lower,
        "entry_zone_high": candidate.entry.upper,
        "ideal_entry": candidate.entry.preferred,
        "maximum_chase_price": candidate.entry.max_chase_price,
        "current_price": candidate.entry.current_price,
        "entry_quality": candidate.quality.entry_quality * 100.0,
        "chase_classification": (
            "EXTENDED" if candidate.entry.is_extended else "WITHIN_LIMITS"
        ),
        "accepted": None,
        "rejected": None,
        "rejection_codes": [],
        "rejection_reasons": [],
        "nearest_future_trigger": _metadata_number(
            metadata,
            "reclaim_trigger",
            "retest_trigger",
            "trigger_price",
        ),
        "near_miss_state": None,
        "invalidation": candidate.invalidation.price,
        "evidence": strategy_evidence_payload(candidate.evidence),
        "evidence_summary": strategy_evidence_summary(candidate.evidence),
    }


def _metadata_number(metadata: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        return float(value)
    return None


def _normalize_routing_config(
    routing_config: Mapping[str, Sequence[str]] | None,
) -> frozenset[StrategyType]:
    source = routing_config or DEFAULT_STRATEGY_ROUTING
    values = source.get("enabled")
    if values is None:
        raise ValueError("strategy routing missing route: enabled")
    strategies = frozenset(StrategyType(value) for value in values)
    if not strategies:
        raise ValueError("strategy routing route cannot be empty: enabled")
    return strategies
