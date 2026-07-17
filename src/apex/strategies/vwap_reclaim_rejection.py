"""Explicit VWAP reclaim or rejection strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


def generate_vwap_reclaim_rejection_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote pullback candidates whose actionable reference is VWAP."""

    if context.decision_frame.features.vwap is None:
        return ()
    candidates = generate_trend_pullback_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_vwap_reclaim_rejection(candidate)
        for candidate in candidates
        if "vwap" in candidate.evidence.feature_references
        and candidate.entry.atr_distance <= 1.25
        and not candidate.entry.is_extended
    )


def _as_vwap_reclaim_rejection(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.VWAP_RECLAIM_REJECTION.value,
        "source_strategy": candidate.strategy.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.VWAP_RECLAIM_REJECTION,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "VWAP provides the active reclaim or rejection reference",
                        "entry remains close enough to VWAP for actionable execution",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple