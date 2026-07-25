"""Stable registry for deterministic strategy candidate generators."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apex.strategies.breakout_continuation import generate_breakout_continuation_candidates
from apex.strategies.breakout_retest import generate_breakout_retest_candidates
from apex.strategies.breakout_routing import (
    BreakoutRoutingResult,
    route_breakout_candidates,
    route_breakout_candidates_with_diagnostics,
)
from apex.strategies.compression_expansion import (
    generate_compression_expansion_candidates,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate
from apex.strategies.exhaustion_reversal import generate_exhaustion_reversal_candidates
from apex.strategies.failed_breakout_reversal import (
    generate_failed_breakout_reversal_candidates,
)
from apex.strategies.first_pullback_continuation import (
    generate_first_pullback_continuation_candidates,
)
from apex.strategies.htf_retest_fallback import (
    generate_htf_aware_trend_pullback_candidates,
)
from apex.strategies.liquidity_rejection_reversal import (
    generate_liquidity_rejection_reversal_candidates,
)
from apex.strategies.momentum_breakout import generate_momentum_breakout_candidates
from apex.strategies.momentum_scalp import generate_momentum_scalp_candidates
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.strategy_types import StrategyType
from apex.strategies.target_ladder import apply_target_ladder_to_candidates
from apex.strategies.vwap_reclaim_rejection import (
    generate_vwap_reclaim_rejection_candidates,
)


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
    (
        StrategyType.TREND_PULLBACK,
        generate_htf_aware_trend_pullback_candidates,
    ),
    (
        StrategyType.COMPRESSION_EXPANSION,
        generate_compression_expansion_candidates,
    ),
    (StrategyType.RANGE_REVERSAL, generate_range_reversal_candidates),
    (
        StrategyType.FAILED_BREAKOUT_REVERSAL,
        generate_failed_breakout_reversal_candidates,
    ),
    (
        StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        generate_liquidity_rejection_reversal_candidates,
    ),
    (
        StrategyType.VWAP_RECLAIM_REJECTION,
        generate_vwap_reclaim_rejection_candidates,
    ),
    (StrategyType.MOMENTUM_SCALP, generate_momentum_scalp_candidates),
    (StrategyType.EXHAUSTION_REVERSAL, generate_exhaustion_reversal_candidates),
)


def _generate_with_target_ladder(
    generator: StrategyGenerator,
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    generated = generator(context, decision_time=decision_time)
    return apply_target_ladder_to_candidates(context, generated)


def run_strategy_generator_with_diagnostics(
    generator: StrategyGenerator,
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> BreakoutRoutingResult:
    """Invoke one generator and preserve shared breakout routing diagnostics."""

    generated = _generate_with_target_ladder(
        generator,
        context,
        decision_time=decision_time,
    )
    return route_breakout_candidates_with_diagnostics(context, generated)


def run_strategy_generator(
    generator: StrategyGenerator,
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Invoke one registered generator and apply shared production routing."""

    generated = _generate_with_target_ladder(
        generator,
        context,
        decision_time=decision_time,
    )
    return route_breakout_candidates(context, generated)
