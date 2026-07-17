"""Explicit exhaustion-reversal strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate, TradeDirection
from apex.strategies.liquidity_rejection_reversal import (
    generate_liquidity_rejection_reversal_candidates,
)
from apex.strategies.strategy_types import StrategyType


def generate_exhaustion_reversal_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote liquidity rejections confirmed by directional RSI exhaustion."""

    rsi = context.decision_frame.features.rsi
    if rsi is None:
        return ()
    candidates = generate_liquidity_rejection_reversal_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_exhaustion_reversal(candidate, rsi=rsi)
        for candidate in candidates
        if _is_exhausted(candidate, rsi=rsi)
    )


def _is_exhausted(candidate: TradeCandidate, *, rsi: float) -> bool:
    if candidate.direction is TradeDirection.LONG:
        return rsi <= 35.0
    return rsi >= 65.0


def _as_exhaustion_reversal(candidate: TradeCandidate, *, rsi: float) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.EXHAUSTION_REVERSAL.value,
        "source_strategy": candidate.strategy.value,
        "exhaustion_rsi": rsi,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.EXHAUSTION_REVERSAL,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        f"RSI exhaustion is confirmed at {rsi:.2f}",
                        "liquidity rejection provides the reversal trigger",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=tuple(
                dict.fromkeys((*evidence.feature_references, "rsi"))
            ),
            structure_references=evidence.structure_references,
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
