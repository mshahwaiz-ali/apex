"""Stable registry for deterministic strategy candidate generators."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apex.strategies.breakout_continuation import generate_breakout_continuation_candidates
from apex.strategies.breakout_retest import generate_breakout_retest_candidates
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate
from apex.strategies.first_pullback_continuation import (
    generate_first_pullback_continuation_candidates,
)
from apex.strategies.liquidity_reversal import generate_liquidity_reversal_candidates
from apex.strategies.momentum_breakout import generate_momentum_breakout_candidates
from apex.strategies.momentum_continuation import generate_momentum_continuation_candidates
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.strategy_types import StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


class StrategyGenerator(Protocol):
    """Typed callable boundary shared by all strategy generators."""

    def __call__(
        self,
        context: StrategyContext,
        *,
        decision_time: datetime,
    ) -> tuple[TradeCandidate, ...]: ...


STRATEGY_REGISTRY: tuple[tuple[StrategyType, StrategyGenerator], ...] = (
    (StrategyType.MOMENTUM_BREAKOUT, generate_momentum_breakout_candidates),
    (StrategyType.BREAKOUT_CONTINUATION, generate_breakout_continuation_candidates),
    (StrategyType.BREAKOUT_RETEST, generate_breakout_retest_candidates),
    (
        StrategyType.FIRST_PULLBACK_CONTINUATION,
        generate_first_pullback_continuation_candidates,
    ),
    (StrategyType.TREND_PULLBACK, generate_trend_pullback_candidates),
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
    """Invoke exactly one registered generator through the typed boundary."""

    return generator(context, decision_time=decision_time)
