"""Soft market-state applicability for Stage 3 strategy evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from apex.strategies.strategy_types import StrategyType
from apex.structure.regime import MarketRegime


class StrategyApplicabilityState(StrEnum):
    APPLICABLE = "applicable"
    CONDITIONAL = "conditional"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class StrategyApplicability:
    strategy: StrategyType
    state: StrategyApplicabilityState
    score: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 100.0:
            raise ValueError("strategy applicability score must be between 0 and 100")
        if not self.reason_codes:
            raise ValueError("strategy applicability reason codes cannot be empty")
        if not self.reasons:
            raise ValueError("strategy applicability reasons cannot be empty")


_TREND = {
    MarketRegime.STRONG_UPTREND,
    MarketRegime.WEAK_UPTREND,
    MarketRegime.STRONG_DOWNTREND,
    MarketRegime.WEAK_DOWNTREND,
}
_RANGE = {
    MarketRegime.STABLE_RANGE,
    MarketRegime.VOLATILE_RANGE,
    MarketRegime.COMPRESSION,
}
_TRANSITION = {MarketRegime.REVERSAL_TRANSITION}
_BREAKOUT = {MarketRegime.BREAKOUT_EXPANSION}
_UNSTABLE = {
    MarketRegime.HIGH_VOLATILITY_CHAOS,
    MarketRegime.LOW_VOLATILITY_STAGNATION,
    MarketRegime.LOW_LIQUIDITY,
    MarketRegime.UNCERTAIN,
}

_STRATEGY_REGIME_PREFERENCES: Mapping[StrategyType, frozenset[MarketRegime]] = {
    StrategyType.MOMENTUM_BREAKOUT: frozenset(_TREND | _BREAKOUT),
    StrategyType.BREAKOUT_CONTINUATION: frozenset(_TREND | _BREAKOUT),
    StrategyType.BREAKOUT_RETEST: frozenset(_TREND | _BREAKOUT | _TRANSITION),
    StrategyType.FIRST_PULLBACK_CONTINUATION: frozenset(_TREND | _BREAKOUT),
    StrategyType.TREND_PULLBACK: frozenset(_TREND | _TRANSITION),
    StrategyType.COMPRESSION_EXPANSION: frozenset({MarketRegime.COMPRESSION} | _BREAKOUT),
    StrategyType.RANGE_REVERSAL: frozenset(_RANGE | _TRANSITION),
    StrategyType.FAILED_BREAKOUT_REVERSAL: frozenset(_RANGE | _TRANSITION),
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: frozenset(_RANGE | _TRANSITION),
    StrategyType.VWAP_RECLAIM_REJECTION: frozenset(_TREND | _RANGE | _TRANSITION),
    StrategyType.MOMENTUM_SCALP: frozenset(_TREND | _BREAKOUT | _TRANSITION),
    StrategyType.EXHAUSTION_REVERSAL: frozenset(_TRANSITION | _BREAKOUT),
}


def build_strategy_applicability(
    *,
    regime: MarketRegime,
    evaluated: tuple[StrategyType, ...],
    eligible: tuple[StrategyType, ...] | None = None,
    higher_timeframe_breakout: bool,
) -> Mapping[StrategyType, StrategyApplicability]:
    """Score regime fit before candidate generation."""

    del eligible
    records: dict[StrategyType, StrategyApplicability] = {}
    for strategy in evaluated:
        preferred = regime in _STRATEGY_REGIME_PREFERENCES.get(strategy, frozenset())
        breakout_support = higher_timeframe_breakout and strategy in {
            StrategyType.MOMENTUM_BREAKOUT,
            StrategyType.BREAKOUT_CONTINUATION,
            StrategyType.BREAKOUT_RETEST,
            StrategyType.FIRST_PULLBACK_CONTINUATION,
            StrategyType.MOMENTUM_SCALP,
        }
        if preferred:
            state = StrategyApplicabilityState.APPLICABLE
            score = 100.0
            code = "REGIME_PREFERRED"
            reason = f"{regime.value} is a preferred regime for {strategy.value}"
        elif breakout_support:
            state = StrategyApplicabilityState.CONDITIONAL
            score = 75.0
            code = "HIGHER_TIMEFRAME_BREAKOUT_SUPPORT"
            reason = (
                "higher-timeframe breakout evidence supports conditional "
                f"{strategy.value} evaluation"
            )
        elif regime in {MarketRegime.HIGH_VOLATILITY_CHAOS, MarketRegime.LOW_LIQUIDITY}:
            state = StrategyApplicabilityState.NOT_APPLICABLE
            score = 0.0
            code = "UNUSABLE_REGIME"
            reason = f"{regime.value} prohibits new {strategy.value} candidate generation"
        elif regime is MarketRegime.LOW_VOLATILITY_STAGNATION and strategy not in {
            StrategyType.COMPRESSION_EXPANSION,
            StrategyType.RANGE_REVERSAL,
        }:
            state = StrategyApplicabilityState.NOT_APPLICABLE
            score = 20.0
            code = "STAGNANT_REGIME"
            reason = f"{regime.value} lacks the movement required by {strategy.value}"
        elif regime in _UNSTABLE:
            state = StrategyApplicabilityState.CONDITIONAL
            score = 35.0
            code = "UNSTABLE_REGIME_PENALTY"
            reason = (
                f"{regime.value} reduces confidence but does not block {strategy.value} evaluation"
            )
        else:
            state = StrategyApplicabilityState.CONDITIONAL
            score = 55.0
            code = "NONCANONICAL_REGIME"
            reason = (
                f"{regime.value} is noncanonical for {strategy.value}; "
                "strategy evidence must justify the candidate"
            )
        records[strategy] = StrategyApplicability(
            strategy=strategy,
            state=state,
            score=score,
            reason_codes=(code,),
            reasons=(reason,),
        )
    return MappingProxyType(records)
