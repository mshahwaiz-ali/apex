"""Explicit compression-expansion strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.breakout_continuation import (
    generate_breakout_continuation_candidates,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.structure.regime import MarketRegime, classify_market_regime


def generate_compression_expansion_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote breakouts emerging from compression or expansion context."""

    regime = classify_market_regime(context.decision_frame.structure)
    if regime not in {MarketRegime.COMPRESSION, MarketRegime.BREAKOUT_EXPANSION}:
        return ()
    candidates = generate_breakout_continuation_candidates(
        context,
        decision_time=decision_time,
    )
    return tuple(_as_compression_expansion(candidate, regime=regime) for candidate in candidates)


def _as_compression_expansion(
    candidate: TradeCandidate,
    *,
    regime: MarketRegime,
) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.COMPRESSION_EXPANSION.value,
        "source_strategy": candidate.strategy.value,
        "compression_expansion_regime": regime.value,
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.COMPRESSION_EXPANSION,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        f"{regime.value} context supports directional expansion",
                        "confirmed breakout provides release from the prior volatility state",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*evidence.structure_references, "compression_expansion"))
            ),
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
