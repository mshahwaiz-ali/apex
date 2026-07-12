"""Phase 4 strategy-candidate orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyType, TradeCandidate
from apex.strategies.registry import STRATEGY_REGISTRY, run_strategy_generator
from apex.structure.regime import MarketRegime, classify_market_regime

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
_TRANSITION_REGIMES = {
    MarketRegime.REVERSAL_TRANSITION,
}
_BREAKOUT_REGIMES = {
    MarketRegime.BREAKOUT_EXPANSION,
}
_UNSTABLE_REGIMES = {
    MarketRegime.HIGH_VOLATILITY_CHAOS,
    MarketRegime.LOW_VOLATILITY_STAGNATION,
    MarketRegime.LOW_LIQUIDITY,
    MarketRegime.UNCERTAIN,
}

_STRATEGY_REGIME_ALLOWLIST: Mapping[StrategyType, frozenset[MarketRegime]] = {
    StrategyType.TREND_PULLBACK: frozenset(_TREND_REGIMES | _TRANSITION_REGIMES),
    StrategyType.BREAKOUT_CONTINUATION: frozenset(_TREND_REGIMES | _BREAKOUT_REGIMES),
    StrategyType.LIQUIDITY_REVERSAL: frozenset(_RANGE_REGIMES | _TRANSITION_REGIMES),
    StrategyType.RANGE_REVERSAL: frozenset(_RANGE_REGIMES | _TRANSITION_REGIMES),
    StrategyType.MOMENTUM_CONTINUATION: frozenset(_TREND_REGIMES | _BREAKOUT_REGIMES),
}


@dataclass(frozen=True, slots=True)
class Phase4AnalysisResult:
    """Immutable collection of raw candidates produced in registry order."""

    symbol: str
    decision_time: datetime
    candidates: tuple[TradeCandidate, ...]
    evaluated_strategies: tuple[StrategyType, ...]
    eligible_strategies: tuple[StrategyType, ...] | None = None
    skipped_strategies: Mapping[StrategyType, str] | None = None
    decision_regime: MarketRegime = MarketRegime.UNCERTAIN

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("analysis-result symbol cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("analysis decision time must be timezone-aware")
        if not self.evaluated_strategies:
            raise ValueError("at least one evaluated strategy is required")
        if len(set(self.evaluated_strategies)) != len(self.evaluated_strategies):
            raise ValueError("evaluated strategies must be unique")
        eligible = (
            self.evaluated_strategies
            if self.eligible_strategies is None
            else self.eligible_strategies
        )
        if len(set(eligible)) != len(eligible):
            raise ValueError("eligible strategies must be unique")
        if any(strategy not in self.evaluated_strategies for strategy in eligible):
            raise ValueError("eligible strategies must be a subset of evaluated strategies")
        skipped = dict(self.skipped_strategies or {})
        if any(strategy not in self.evaluated_strategies for strategy in skipped):
            raise ValueError("skipped strategies must be a subset of evaluated strategies")
        if any(strategy in eligible for strategy in skipped):
            raise ValueError("strategy cannot be both eligible and skipped")

        for candidate in self.candidates:
            if candidate.symbol != self.symbol:
                raise ValueError("candidate symbol must match the analysis symbol")
            if candidate.decision_time != self.decision_time:
                raise ValueError("candidate decision time must match the analysis decision time")
            if candidate.strategy not in self.evaluated_strategies:
                raise ValueError("candidate strategy must be present in evaluated strategies")
            if candidate.strategy not in eligible:
                raise ValueError("candidate strategy must be eligible for the decision regime")

        candidate_strategies = tuple(item.strategy for item in self.candidates)
        expected_order = tuple(sorted(candidate_strategies, key=self.evaluated_strategies.index))
        if candidate_strategies != expected_order:
            raise ValueError("candidates must preserve stable registry ordering")
        object.__setattr__(self, "eligible_strategies", eligible)
        object.__setattr__(self, "skipped_strategies", MappingProxyType(skipped))


def analyze_phase4(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> Phase4AnalysisResult:
    """Run all candidate generators without ranking or selecting a winning trade."""

    evaluated = tuple(strategy for strategy, _generator in STRATEGY_REGISTRY)
    decision_regime = classify_market_regime(context.decision_frame.structure)
    eligible, skipped = _strategy_eligibility(decision_regime, evaluated)
    candidates = tuple(
        candidate
        for _strategy, generator in STRATEGY_REGISTRY
        if _strategy in eligible
        for candidate in run_strategy_generator(
            generator,
            context,
            decision_time=decision_time,
        )
    )
    return Phase4AnalysisResult(
        symbol=context.symbol,
        decision_time=decision_time,
        candidates=candidates,
        evaluated_strategies=evaluated,
        eligible_strategies=eligible,
        skipped_strategies=skipped,
        decision_regime=decision_regime,
    )


def _strategy_eligibility(
    regime: MarketRegime,
    evaluated: tuple[StrategyType, ...],
) -> tuple[tuple[StrategyType, ...], Mapping[StrategyType, str]]:
    if regime in _UNSTABLE_REGIMES:
        return (), {
            strategy: f"decision regime {regime.value} is not eligible for candidate generation"
            for strategy in evaluated
        }

    eligible: list[StrategyType] = []
    skipped: dict[StrategyType, str] = {}
    for strategy in evaluated:
        allowed = _STRATEGY_REGIME_ALLOWLIST[strategy]
        if regime in allowed:
            eligible.append(strategy)
        else:
            skipped[strategy] = (
                f"decision regime {regime.value} is outside {strategy.value} eligibility"
            )
    return tuple(eligible), skipped
