"""Shared production routing for breakout strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.strategies.timeframe_authority import resolve_breakout_direction_authority

_BREAKOUT_FAMILIES = {
    StrategyType.BREAKOUT_RETEST,
    StrategyType.BREAKOUT_CONTINUATION,
    StrategyType.MOMENTUM_BREAKOUT,
}


@dataclass(frozen=True, slots=True)
class BreakoutRoutingRejection:
    """One breakout candidate rejected by deterministic timeframe authority."""

    candidate: TradeCandidate
    reason_code: str


@dataclass(frozen=True, slots=True)
class BreakoutRoutingResult:
    """Retained and rejected candidates from the shared breakout router."""

    candidates: tuple[TradeCandidate, ...]
    rejected: tuple[BreakoutRoutingRejection, ...]
    raw_breakout_candidate_count: int
    conditional_candidate_count: int


def route_breakout_candidates_with_diagnostics(
    context: StrategyContext,
    candidates: tuple[TradeCandidate, ...],
) -> BreakoutRoutingResult:
    """Apply deterministic authority rules while preserving rejection lineage."""

    routed: list[TradeCandidate] = []
    rejected: list[BreakoutRoutingRejection] = []
    raw_breakout_candidate_count = 0
    conditional_candidate_count = 0

    for candidate in candidates:
        if candidate.strategy not in _BREAKOUT_FAMILIES:
            routed.append(candidate)
            continue

        raw_breakout_candidate_count += 1
        authority = resolve_breakout_direction_authority(context, candidate)
        metadata = {**dict(candidate.metadata), **authority.metadata()}
        if not authority.allowed:
            rejected.append(
                BreakoutRoutingRejection(
                    candidate=replace(candidate, metadata=metadata),
                    reason_code=authority.routing_rejection_reason or "breakout_authority_rejected",
                )
            )
            continue

        warnings = list(candidate.evidence.warnings)
        provisional = candidate.provisional
        if authority.conditional_only:
            conditional_candidate_count += 1
            warnings.append(
                "3m refinement strongly opposes immediate continuation; wait for renewal"
            )
            metadata["entry_confirmation_complete"] = False
            metadata["refinement_requires_renewal"] = True
            provisional = True

        routed.append(
            replace(
                candidate,
                metadata=metadata,
                provisional=provisional,
                evidence=StrategyEvidence(
                    supporting=candidate.evidence.supporting,
                    contradictions=candidate.evidence.contradictions,
                    warnings=tuple(dict.fromkeys(warnings)),
                    feature_references=candidate.evidence.feature_references,
                    structure_references=candidate.evidence.structure_references,
                    liquidity_references=candidate.evidence.liquidity_references,
                ),
            )
        )

    return BreakoutRoutingResult(
        candidates=tuple(routed),
        rejected=tuple(rejected),
        raw_breakout_candidate_count=raw_breakout_candidate_count,
        conditional_candidate_count=conditional_candidate_count,
    )


def route_breakout_candidates(
    context: StrategyContext,
    candidates: tuple[TradeCandidate, ...],
) -> tuple[TradeCandidate, ...]:
    """Apply the same deterministic authority rules to scan, analyze and backtest."""

    return route_breakout_candidates_with_diagnostics(context, candidates).candidates
