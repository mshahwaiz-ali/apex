"""Explicit breakout-retest strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.higher_timeframe_breakout import (
    generate_higher_timeframe_breakout_retest_candidates,
)
from apex.strategies.strategy_types import StrategyType


def generate_breakout_retest_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Generate transparent retest candidates from confirmed breakout context."""

    candidates = generate_higher_timeframe_breakout_retest_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(_as_breakout_retest(candidate) for candidate in candidates)


def _as_breakout_retest(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.BREAKOUT_RETEST.value,
        "source_strategy": candidate.strategy.value,
    }
    return replace(
        candidate,
        strategy=StrategyType.BREAKOUT_RETEST,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "confirmed breakout context is being retested",
                        *candidate.evidence.supporting,
                    )
                )
            ),
            contradictions=candidate.evidence.contradictions,
            warnings=candidate.evidence.warnings,
            feature_references=candidate.evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*candidate.evidence.structure_references, "breakout_retest"))
            ),
            liquidity_references=candidate.evidence.liquidity_references,
        ),
        metadata=metadata,
    )
