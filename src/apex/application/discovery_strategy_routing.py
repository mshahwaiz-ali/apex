"""Stage 3 strategy enablement and transparent routing diagnostics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.strategies import (
    CandidateActionability,
    EntryStatus,
    StrategyAnalysisResult,
    StrategyType,
    SuppressedStrategyCandidate,
    TradeCandidate,
    strategy_evidence_payload,
    strategy_evidence_summary,
)
from apex.strategies.candidate_identity import candidate_identities

_BREAKOUT_STRATEGIES = {
    StrategyType.MOMENTUM_BREAKOUT,
    StrategyType.BREAKOUT_CONTINUATION,
    StrategyType.BREAKOUT_RETEST,
}
_BREAKOUT_ROUTING_STAGE = "breakout_timeframe_authority"


def apply_strategy_routing(
    strategy_analysis: StrategyAnalysisResult,
    *,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> StrategyAnalysisResult:
    """Apply only explicit strategy enablement; default to every evaluated family."""

    enabled = _enabled_strategies(
        strategy_analysis.evaluated_strategies,
        routing_config,
    )
    enabled_candidates_with_status = tuple(
        entry
        for entry in strategy_analysis.candidate_actionability
        if entry.candidate.strategy in enabled
    )
    candidates = tuple(entry.candidate for entry in enabled_candidates_with_status)
    candidate_actionability = tuple(
        CandidateActionability(candidate=entry.candidate, status=entry.status)
        for entry in enabled_candidates_with_status
    )
    identity_by_object = dict(
        zip(
            map(id, strategy_analysis.candidates),
            candidate_identities(strategy_analysis.candidates),
            strict=True,
        )
    )
    status_by_object = {
        id(entry.candidate): entry.status for entry in strategy_analysis.candidate_actionability
    }
    newly_suppressed = tuple(
        SuppressedStrategyCandidate(
            candidate=candidate,
            reason_codes=("STRATEGY_EXPLICITLY_DISABLED",),
            reasons=(f"{candidate.strategy.value} is disabled by explicit strategy configuration",),
            candidate_id=identity_by_object[id(candidate)],
            entry_status=status_by_object.get(id(candidate)),
            suppression_stage="strategy_enablement",
        )
        for candidate in strategy_analysis.candidates
        if candidate.strategy not in enabled
    )
    skipped = {
        strategy: f"{strategy.value} is disabled by explicit strategy configuration"
        for strategy in strategy_analysis.evaluated_strategies
        if strategy not in enabled
    }
    return StrategyAnalysisResult(
        symbol=strategy_analysis.symbol,
        decision_time=strategy_analysis.decision_time,
        candidates=candidates,
        evaluated_strategies=strategy_analysis.evaluated_strategies,
        eligible_strategies=enabled,
        skipped_strategies=skipped,
        strategy_diagnostics=strategy_analysis.strategy_diagnostics,
        decision_regime=strategy_analysis.decision_regime,
        higher_timeframe_breakout=strategy_analysis.higher_timeframe_breakout,
        strategy_applicability=strategy_analysis.strategy_applicability,
        candidate_actionability=candidate_actionability,
        suppressed_candidates=(strategy_analysis.suppressed_candidates + newly_suppressed),
    )


def build_strategy_routing_payload(
    *,
    assessment: DiscoveryAssessment,
    strategy_analysis: StrategyAnalysisResult | None = None,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Return Stage 3 strategy diagnostics without mode or regime gating."""

    evaluated = (
        strategy_analysis.evaluated_strategies
        if strategy_analysis is not None
        else tuple(StrategyType)
    )
    enabled = _enabled_strategies(evaluated, routing_config)
    disabled = tuple(strategy for strategy in evaluated if strategy not in enabled)
    setup = assessment.setup
    selected = setup.strategy if setup is not None else None
    diagnostics = _strategy_diagnostics(strategy_analysis)
    return {
        "enabled_strategies": [strategy.value for strategy in enabled],
        "disabled_strategies": [strategy.value for strategy in disabled],
        "selected_strategy": selected.value if selected is not None else None,
        "selected_strategy_enabled": selected in enabled if selected is not None else False,
        "decision_regime": (
            strategy_analysis.decision_regime.value if strategy_analysis is not None else None
        ),
        "higher_timeframe_breakout": (
            strategy_analysis.higher_timeframe_breakout if strategy_analysis is not None else False
        ),
        "routed_eligible_strategies": [strategy.value for strategy in enabled],
        "skipped_strategies": (
            {
                strategy.value: reason
                for strategy, reason in strategy_analysis.skipped_strategies.items()
            }
            if strategy_analysis is not None and strategy_analysis.skipped_strategies is not None
            else {}
        ),
        "strategy_diagnostics": diagnostics,
        "strategy_applicability": _applicability_payload(strategy_analysis),
        "breakout_routing": _breakout_routing_summary(strategy_analysis),
        "suppressed_candidates": _suppressed_payload(strategy_analysis),
        "candidate_diagnostics": _candidate_payloads(strategy_analysis),
        "eligible": setup is not None,
        "reasons": ["all evaluated strategies enabled unless explicitly disabled"],
        "rejections": list(assessment.reasons),
    }


def _enabled_strategies(
    evaluated: Sequence[StrategyType],
    routing_config: Mapping[str, Sequence[str]] | None,
) -> tuple[StrategyType, ...]:
    if routing_config is None:
        return tuple(evaluated)
    values = routing_config.get("enabled")
    if values is None:
        raise ValueError("strategy configuration missing enabled strategies")
    requested = frozenset(StrategyType(value) for value in values)
    if not requested:
        raise ValueError("enabled strategy configuration cannot be empty")
    return tuple(strategy for strategy in evaluated if strategy in requested)


def _strategy_diagnostics(
    analysis: StrategyAnalysisResult | None,
) -> dict[str, object]:
    if analysis is None or analysis.strategy_diagnostics is None:
        return {}
    return {
        strategy.value: {
            "candidate_count": diagnostic.candidate_count,
            "rejection_codes": [code.value for code in diagnostic.rejection_codes],
            "reasons": list(diagnostic.reasons),
            "near_miss_state": diagnostic.near_miss_state.value,
            "higher_timeframe_breakout": diagnostic.higher_timeframe_breakout,
        }
        for strategy, diagnostic in analysis.strategy_diagnostics.items()
    }


def _breakout_routing_summary(
    analysis: StrategyAnalysisResult | None,
) -> dict[str, object]:
    if analysis is None:
        return {
            "raw_breakout_candidate_count": 0,
            "routed_breakout_candidate_count": 0,
            "rejected_breakout_candidate_count": 0,
            "conditional_breakout_candidate_count": 0,
            "rejection_counts": {},
            "timing_frame_direction_violation_count": 0,
        }

    retained_breakouts = tuple(
        candidate
        for candidate in analysis.candidates
        if candidate.strategy in _BREAKOUT_STRATEGIES
    )
    rejected_breakouts = tuple(
        item
        for item in analysis.suppressed_candidates
        if item.suppression_stage == _BREAKOUT_ROUTING_STAGE
    )
    rejection_counts = Counter(
        code
        for item in rejected_breakouts
        for code in item.reason_codes
    )
    conditional_count = sum(
        bool(candidate.metadata.get("refinement_requires_renewal"))
        for candidate in retained_breakouts
    )
    timing_violation_count = sum(
        candidate.metadata.get("timing_frame_used_for_direction") is not False
        for candidate in retained_breakouts
    ) + sum(
        item.candidate.metadata.get("timing_frame_used_for_direction") is not False
        for item in rejected_breakouts
    )
    return {
        "raw_breakout_candidate_count": len(retained_breakouts) + len(rejected_breakouts),
        "routed_breakout_candidate_count": len(retained_breakouts),
        "rejected_breakout_candidate_count": len(rejected_breakouts),
        "conditional_breakout_candidate_count": conditional_count,
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "direction_authority_opposed_count": rejection_counts.get(
            "30m_direction_authority_opposed", 0
        ),
        "setup_authority_opposed_count": rejection_counts.get(
            "15m_setup_authority_opposed", 0
        ),
        "retest_failed_count": rejection_counts.get("5m_retest_failed", 0),
        "retest_not_accepted_count": rejection_counts.get(
            "5m_retest_not_accepted", 0
        ),
        "execution_authority_opposed_count": rejection_counts.get(
            "5m_execution_authority_opposed", 0
        ),
        "timing_frame_direction_violation_count": timing_violation_count,
    }


def _applicability_payload(
    analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if analysis is None:
        return []
    applicability = analysis.strategy_applicability or {}
    enabled = frozenset(analysis.eligible_strategies or ())
    return [
        {
            "strategy": strategy.value,
            "state": record.state.value,
            "score": record.score,
            "reason_codes": list(record.reason_codes),
            "reasons": list(record.reasons),
            "enabled": strategy in enabled,
        }
        for strategy in analysis.evaluated_strategies
        if (record := applicability.get(strategy)) is not None
    ]


def _suppressed_payload(
    analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if analysis is None:
        return []
    return [
        {
            **_candidate_payload(item.candidate, status=item.entry_status),
            "candidate_id": item.candidate_id,
            "routing_status": "suppressed",
            "suppression_stage": item.suppression_stage,
            "reason_codes": list(item.reason_codes),
            "reasons": list(item.reasons),
        }
        for item in analysis.suppressed_candidates
    ]


def _candidate_payloads(
    analysis: StrategyAnalysisResult | None,
) -> list[dict[str, object]]:
    if analysis is None:
        return []
    records = [
        _candidate_payload(entry.candidate, status=entry.status)
        for entry in analysis.candidate_actionability
    ]
    produced = {candidate.strategy for candidate in analysis.candidates}
    diagnostics = analysis.strategy_diagnostics or {}
    for strategy in analysis.evaluated_strategies:
        if strategy in produced:
            continue
        diagnostic = diagnostics.get(strategy)
        records.append(
            {
                "strategy": strategy.value,
                "direction": None,
                "generated": False,
                "entry_status": (
                    diagnostic.near_miss_state.value if diagnostic is not None else None
                ),
                "rejection_codes": (
                    [code.value for code in diagnostic.rejection_codes]
                    if diagnostic is not None
                    else []
                ),
                "rejection_reasons": (list(diagnostic.reasons) if diagnostic is not None else []),
                "near_miss_state": (
                    diagnostic.near_miss_state.value if diagnostic is not None else None
                ),
            }
        )
    return records


def _candidate_payload(
    candidate: TradeCandidate,
    *,
    status: EntryStatus | None,
) -> dict[str, object]:
    return {
        "strategy": candidate.strategy.value,
        "direction": candidate.direction.value,
        "generated": True,
        "entry_status": status.value if status is not None else None,
        "entry_zone_low": candidate.entry.lower,
        "entry_zone_high": candidate.entry.upper,
        "ideal_entry": candidate.entry.preferred,
        "maximum_chase_price": candidate.entry.max_chase_price,
        "current_price": candidate.entry.current_price,
        "entry_quality": candidate.quality.entry_quality * 100.0,
        "invalidation": candidate.invalidation.price,
        "metadata": dict(candidate.metadata),
        "evidence": strategy_evidence_payload(candidate.evidence),
        "evidence_summary": strategy_evidence_summary(candidate.evidence),
    }
