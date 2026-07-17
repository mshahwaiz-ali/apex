"""Soft market-state applicability for strategy evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from apex.strategies.contracts import StrategyType
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


_TREND_REGIMES = {
    MarketRegime.STRONG_UPTREND,
    MarketRegime.WEAK_UPTREND,
    MarketRegime.STRONG_DOWNTREND,
    MarketRegime.WEAK_DOWNTREND,
}
_RANGE_REGIMES = {
    MarketRegime.STABLE_RANGE,
    MarketRegime.VOLATILE_RANGE,
    MarketRegime.COMPRESSION,
}
_TRANSITION_REGIMES = {MarketRegime.REVERSAL_TRANSITION}
_BREAKOUT_REGIMES = {MarketRegime.BREAKOUT_EXPANSION}
_UNSTABLE_REGIMES = {
    MarketRegime.HIGH_VOLATILITY_CHAOS,
    MarketRegime.LOW_VOLATILITY_STAGNATION,
    MarketRegime.LOW_LIQUIDITY,
    MarketRegime.UNCERTAIN,
}

_STRATEGY_REGIME_PREFERENCES: Mapping[StrategyType, frozenset[MarketRegime]] = {
    StrategyType.TREND_PULLBACK: frozenset(_TREND_REGIMES | _TRANSITION_REGIMES),
    StrategyType.BREAKOUT_CONTINUATION: frozenset(_TREND_REGIMES | _BREAKOUT_REGIMES),
    StrategyType.LIQUIDITY_REVERSAL: frozenset(_RANGE_REGIMES | _TRANSITION_REGIMES),
    StrategyType.RANGE_REVERSAL: frozenset(_RANGE_REGIMES | _TRANSITION_REGIMES),
    StrategyType.MOMENTUM_CONTINUATION: frozenset(_TREND_REGIMES | _BREAKOUT_REGIMES),
}


def build_strategy_applicability(
    *,
    regime: MarketRegime,
    evaluated: tuple[StrategyType, ...],
    eligible: tuple[StrategyType, ...] | None = None,
    higher_timeframe_breakout: bool,
) -> Mapping[StrategyType, StrategyApplicability]:
    """Score regime fit without preventing a strategy generator from running."""

    del eligible
    records: dict[StrategyType, StrategyApplicability] = {}
    for strategy in evaluated:
        preferred = regime in _STRATEGY_REGIME_PREFERENCES[strategy]
        breakout_support = higher_timeframe_breakout and strategy in {
            StrategyType.BREAKOUT_CONTINUATION,
            StrategyType.MOMENTUM_CONTINUATION,
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
        elif regime in _UNSTABLE_REGIMES:
            state = StrategyApplicabilityState.CONDITIONAL
            score = 35.0
            code = "UNSTABLE_REGIME_PENALTY"
            reason = (
                f"{regime.value} reduces confidence but does not block "
                f"{strategy.value} evaluation"
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
