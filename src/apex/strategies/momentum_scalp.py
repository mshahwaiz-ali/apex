"""Explicit near-CMP momentum-scalp strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.momentum_continuation import (
    generate_momentum_continuation_candidates,
)
from apex.strategies.strategy_types import StrategyType


def generate_momentum_scalp_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote only immediate, tight-geometry momentum candidates."""

    candidates = generate_momentum_continuation_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_momentum_scalp(candidate)
        for candidate in candidates
        if candidate.entry.atr_distance <= 0.6
        and candidate.entry.location_quality >= 0.65
        and not candidate.entry.is_extended
    )


def _as_momentum_scalp(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.MOMENTUM_SCALP.value,
        "source_strategy": candidate.strategy.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.MOMENTUM_SCALP,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "entry is within a tight ATR distance of current price",
                        "location quality supports an immediate momentum scalp",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=evidence.structure_references,
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
