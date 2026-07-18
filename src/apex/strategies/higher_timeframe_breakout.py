"""Higher-timeframe breakout with lower-timeframe retest continuation fallback."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.diagnostics import has_higher_timeframe_breakout
from apex.strategies.strategy_types import StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


def generate_higher_timeframe_breakout_retest_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote valid lower-timeframe pullbacks under higher-timeframe breakout context."""

    if not has_higher_timeframe_breakout(context):
        return ()

    pullbacks = generate_trend_pullback_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(_promote_candidate(candidate) for candidate in pullbacks)


def _promote_candidate(candidate: TradeCandidate) -> TradeCandidate:
    supporting = tuple(
        dict.fromkeys(
            (
                "higher-timeframe breakout expansion establishes continuation context",
                "lower-timeframe structure provides the retest or reclaim execution geometry",
                *candidate.evidence.supporting,
            )
        )
    )
    metadata = {
        **dict(candidate.metadata),
        "higher_timeframe_breakout_continuation": True,
        "source_strategy": candidate.strategy.value,
    }
    return replace(
        candidate,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence=StrategyEvidence(
            supporting=supporting,
            contradictions=candidate.evidence.contradictions,
            warnings=candidate.evidence.warnings,
            feature_references=candidate.evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys(
                    (*candidate.evidence.structure_references, "higher_timeframe_breakout")
                )
            ),
            liquidity_references=candidate.evidence.liquidity_references,
        ),
        metadata=metadata,
    )
