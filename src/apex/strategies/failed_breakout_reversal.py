"""Explicit failed-breakout reversal strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.strategy_types import StrategyType

_FALSE_BREAK_EVIDENCE = "confirmed false-break state supports rejection back into the range"


def generate_failed_breakout_reversal_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote range candidates backed by a confirmed failed breakout."""

    candidates = generate_range_reversal_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_failed_breakout(candidate)
        for candidate in candidates
        if _FALSE_BREAK_EVIDENCE in candidate.evidence.supporting
    )


def _as_failed_breakout(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.FAILED_BREAKOUT_REVERSAL.value,
        "source_strategy": candidate.strategy.value,
        "confirmed_failed_breakout": True,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.FAILED_BREAKOUT_REVERSAL,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "failed breakout rejected beyond the range boundary",
                        "price returned into the prior range before entry selection",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*evidence.structure_references, "failed_breakout"))
            ),
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
