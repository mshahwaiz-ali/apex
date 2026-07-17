"""Explicit first-pullback continuation strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


def generate_first_pullback_continuation_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote near-CMP pullbacks with a concrete continuation reference."""

    candidates = generate_trend_pullback_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(
        _as_first_pullback(candidate)
        for candidate in candidates
        if int(candidate.metadata.get("reference_count", 0)) >= 1
        and candidate.entry.atr_distance <= 1.0
        and not candidate.entry.is_extended
    )


def _as_first_pullback(candidate: TradeCandidate) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.FIRST_PULLBACK_CONTINUATION.value,
        "source_strategy": candidate.strategy.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.FIRST_PULLBACK_CONTINUATION,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "first actionable pullback remains close to current price",
                        "at least one structural, EMA, or VWAP continuation reference is present",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*evidence.structure_references, "first_pullback"))
            ),
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
