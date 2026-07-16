"""Stable registry for deterministic Phase 4 strategy generators."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apex.strategies.breakout_continuation import generate_breakout_continuation_candidates
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyType, TradeCandidate
from apex.strategies.higher_timeframe_breakout import (
    generate_higher_timeframe_breakout_retest_candidates,
)
from apex.strategies.liquidity_reversal import generate_liquidity_reversal_candidates
from apex.strategies.momentum_continuation import generate_momentum_continuation_candidates
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


class StrategyGenerator(Protocol):
    """Typed callable boundary shared by all Phase 4 generators."""

    def __call__(
        self,
        context: StrategyContext,
        *,
        decision_time: datetime,
    ) -> tuple[TradeCandidate, ...]: ...


STRATEGY_REGISTRY: tuple[tuple[StrategyType, StrategyGenerator], ...] = (
    (StrategyType.TREND_PULLBACK, generate_trend_pullback_candidates),
    (StrategyType.BREAKOUT_CONTINUATION, generate_breakout_continuation_candidates),
    (StrategyType.LIQUIDITY_REVERSAL, generate_liquidity_reversal_candidates),
    (StrategyType.RANGE_REVERSAL, generate_range_reversal_candidates),
    (StrategyType.MOMENTUM_CONTINUATION, generate_momentum_continuation_candidates),
)


def run_strategy_generator(
    generator: StrategyGenerator,
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Invoke one registered generator through a single typed orchestration boundary."""

    candidates = generator(context, decision_time=decision_time)
    if candidates or generator is not generate_breakout_continuation_candidates:
        return candidates
    return generate_higher_timeframe_breakout_retest_candidates(
        context,
        decision_time=decision_time,
    )
