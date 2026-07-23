"""Shared production routing for breakout strategy candidates."""

from __future__ import annotations

from dataclasses import replace

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.strategies.timeframe_authority import resolve_breakout_direction_authority

_BREAKOUT_FAMILIES = {
    StrategyType.BREAKOUT_RETEST,
    StrategyType.BREAKOUT_CONTINUATION,
    StrategyType.MOMENTUM_BREAKOUT,
}


def route_breakout_candidates(
    context: StrategyContext,
    candidates: tuple[TradeCandidate, ...],
) -> tuple[TradeCandidate, ...]:
    """Apply the same deterministic authority rules to scan, analyze and backtest."""

    routed: list[TradeCandidate] = []
    for candidate in candidates:
        if candidate.strategy not in _BREAKOUT_FAMILIES:
            routed.append(candidate)
            continue

        authority = resolve_breakout_direction_authority(context, candidate)
        metadata = {**dict(candidate.metadata), **authority.metadata()}
        if not authority.allowed:
            continue

        warnings = list(candidate.evidence.warnings)
        provisional = candidate.provisional
        if authority.conditional_only:
            warnings.append("3m refinement strongly opposes immediate continuation; wait for renewal")
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
    return tuple(routed)
