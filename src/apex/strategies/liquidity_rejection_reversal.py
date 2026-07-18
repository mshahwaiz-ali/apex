"""Explicit liquidity-rejection reversal strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.liquidity_reversal import generate_liquidity_reversal_candidates
from apex.strategies.strategy_types import StrategyType


def generate_liquidity_rejection_reversal_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Expose confirmed sweep, trap, and boundary recovery as one family."""

    candidates = generate_liquidity_reversal_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(_as_liquidity_rejection(candidate) for candidate in candidates)


def _as_liquidity_rejection(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.LIQUIDITY_REJECTION_REVERSAL.value,
        "source_strategy": candidate.strategy.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "confirmed liquidity sweep and trap rejection define the reversal",
                        "price recovered the swept boundary before entry selection",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=evidence.structure_references,
            liquidity_references=tuple(
                dict.fromkeys((*evidence.liquidity_references, "liquidity_rejection_reversal"))
            ),
        ),
        metadata=metadata,
    )
