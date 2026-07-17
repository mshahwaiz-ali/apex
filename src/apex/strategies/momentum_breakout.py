"""Explicit momentum-breakout strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.momentum_continuation import (
    generate_momentum_continuation_candidates,
)
from apex.strategies.strategy_types import StrategyType


def generate_momentum_breakout_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Return momentum candidates backed by a confirmed structural break."""

    candidates = generate_momentum_continuation_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_momentum_breakout(candidate)
        for candidate in candidates
        if candidate.metadata.get("recent_continuation_break") is True
    )


def _as_momentum_breakout(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.MOMENTUM_BREAKOUT.value,
        "source_strategy": candidate.strategy.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "confirmed structural break supports immediate momentum expansion",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*evidence.structure_references, "momentum_breakout"))
            ),
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
