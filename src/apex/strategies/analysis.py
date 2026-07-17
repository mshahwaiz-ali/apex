"""Phase 4 strategy-candidate orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime
from types import MappingProxyType

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyType, TradeCandidate
from apex.strategies.diagnostics import (
    StrategyDiagnostic,
    build_phase4_diagnostics,
    has_higher_timeframe_breakout,
)
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
_TRANSITION_REGIMES = {MarketRegime.REVERSAL_TRANSITION}
_BREAKOUT_REGIMES = {MarketRegime.BREAKOUT_EXPANSION}
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



@dataclass(frozen=True, slots=True)
class SuppressedStrategyCandidate:
    """Generated candidate retained for audit but excluded downstream."""

    candidate: TradeCandidate
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError(
                "suppressed candidate reason codes cannot be empty"
            )
        if not self.reasons:
            raise ValueError(
                "suppressed candidate reasons cannot be empty"
            )


@dataclass(frozen=True, slots=True)
class Phase4AnalysisResult:
    """Immutable collection of raw candidates produced in registry order."""

    symbol: str
    decision_time: datetime
    candidates: tuple[TradeCandidate, ...]
    evaluated_strategies: tuple[StrategyType, ...]
    eligible_strategies: tuple[StrategyType, ...] | None = None
    skipped_strategies: Mapping[StrategyType, str] | None = None
    strategy_diagnostics: Mapping[StrategyType, StrategyDiagnostic] | None = None
    decision_regime: MarketRegime = MarketRegime.UNCERTAIN
    higher_timeframe_breakout: bool = False
    strategy_applicability: Mapping[
        StrategyType, StrategyApplicability
    ] | None = None
    suppressed_candidates: tuple[
        SuppressedStrategyCandidate, ...
    ] = ()

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
        diagnostics = dict(self.strategy_diagnostics or {})
        if any(strategy not in self.evaluated_strategies for strategy in diagnostics):
            raise ValueError("strategy diagnostics must be a subset of evaluated strategies")
        applicability = dict(self.strategy_applicability or {})
        if any(strategy not in self.evaluated_strategies for strategy in applicability):
            raise ValueError(
                "strategy applicability must be a subset of evaluated strategies"
            )
        if applicability and set(applicability) != set(self.evaluated_strategies):
            raise ValueError(
                "strategy applicability must cover every evaluated strategy"
            )

        for suppressed in self.suppressed_candidates:
            candidate = suppressed.candidate
            if candidate.symbol != self.symbol:
                raise ValueError(
                    "suppressed candidate symbol must match the analysis symbol"
                )
            if candidate.decision_time != self.decision_time:
                raise ValueError(
                    "suppressed candidate decision time must match the analysis "
                    "decision time"
                )
            if candidate.strategy not in self.evaluated_strategies:
                raise ValueError(
                    "suppressed candidate strategy must be evaluated"
                )

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
        object.__setattr__(self, "strategy_diagnostics", MappingProxyType(diagnostics))
        object.__setattr__(
            self,
            "strategy_applicability",
            MappingProxyType(applicability),
        )


def analyze_phase4(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> Phase4AnalysisResult:
    """Run all candidate generators without ranking or selecting a winning trade."""

    evaluated = tuple(strategy for strategy, _generator in STRATEGY_REGISTRY)
    decision_regime = classify_market_regime(context.decision_frame.structure)
    higher_breakout = has_higher_timeframe_breakout(context)
    eligible, skipped = _strategy_eligibility(
        decision_regime,
        evaluated,
        higher_timeframe_breakout=higher_breakout,
    )
    candidates = tuple(
        candidate
        for strategy, generator in STRATEGY_REGISTRY
        if strategy in eligible
        for candidate in run_strategy_generator(
            generator,
            context,
            decision_time=decision_time,
        )
    )
    diagnostics = build_phase4_diagnostics(
        context,
        evaluated=evaluated,
        eligible=eligible,
        skipped=skipped,
        candidates=candidates,
    )
    applicability = build_strategy_applicability(
        regime=decision_regime,
        evaluated=evaluated,
        eligible=eligible,
        higher_timeframe_breakout=higher_breakout,
    )
    return Phase4AnalysisResult(
        symbol=context.symbol,
        decision_time=decision_time,
        candidates=candidates,
        evaluated_strategies=evaluated,
        eligible_strategies=eligible,
        skipped_strategies=skipped,
        strategy_diagnostics=diagnostics,
        decision_regime=decision_regime,
        higher_timeframe_breakout=higher_breakout,
        strategy_applicability=applicability,
    )


def build_strategy_applicability(
    *,
    regime: MarketRegime,
    evaluated: tuple[StrategyType, ...],
    eligible: tuple[StrategyType, ...],
    higher_timeframe_breakout: bool,
) -> Mapping[StrategyType, StrategyApplicability]:
    records: dict[StrategyType, StrategyApplicability] = {}
    for strategy in evaluated:
        canonical = regime in _STRATEGY_REGIME_ALLOWLIST[strategy]
        breakout_override = (
            higher_timeframe_breakout
            and strategy
            in {
                StrategyType.BREAKOUT_CONTINUATION,
                StrategyType.MOMENTUM_CONTINUATION,
            }
            and not canonical
        )
        if canonical:
            records[strategy] = StrategyApplicability(
                strategy=strategy,
                state=StrategyApplicabilityState.APPLICABLE,
                score=100.0,
                reason_codes=("REGIME_APPLICABLE",),
                reasons=(
                    f"{regime.value} is a canonical regime for {strategy.value}",
                ),
            )
        elif breakout_override and strategy in eligible:
            records[strategy] = StrategyApplicability(
                strategy=strategy,
                state=StrategyApplicabilityState.CONDITIONAL,
                score=65.0,
                reason_codes=("HIGHER_TIMEFRAME_BREAKOUT_OVERRIDE",),
                reasons=(
                    "higher-timeframe breakout evidence conditionally enabled "
                    f"{strategy.value} outside its canonical decision regime",
                ),
            )
        else:
            records[strategy] = StrategyApplicability(
                strategy=strategy,
                state=StrategyApplicabilityState.NOT_APPLICABLE,
                score=0.0,
                reason_codes=("REGIME_NOT_APPLICABLE",),
                reasons=(
                    f"{regime.value} is outside {strategy.value} applicability",
                ),
            )
    return MappingProxyType(records)


def _strategy_eligibility(
    regime: MarketRegime,
    evaluated: tuple[StrategyType, ...],
    *,
    higher_timeframe_breakout: bool = False,
) -> tuple[tuple[StrategyType, ...], Mapping[StrategyType, str]]:
    if regime in _UNSTABLE_REGIMES:
        if not higher_timeframe_breakout:
            return (), {
                strategy: f"decision regime {regime.value} is not eligible for candidate generation"
                for strategy in evaluated
            }
        continuation = {
            StrategyType.BREAKOUT_CONTINUATION,
            StrategyType.MOMENTUM_CONTINUATION,
        }
        continuation_eligible = tuple(
            strategy for strategy in evaluated if strategy in continuation
        )
        continuation_skipped = {
            strategy: (
                f"decision regime {regime.value} is only eligible for higher-timeframe "
                "breakout continuation routing"
            )
            for strategy in evaluated
            if strategy not in continuation
        }
        return continuation_eligible, continuation_skipped

    eligible_strategies: list[StrategyType] = []
    skipped_strategies: dict[StrategyType, str] = {}
    for strategy in evaluated:
        allowed = _STRATEGY_REGIME_ALLOWLIST[strategy]
        if regime in allowed or (
            higher_timeframe_breakout
            and strategy
            in {
                StrategyType.BREAKOUT_CONTINUATION,
                StrategyType.MOMENTUM_CONTINUATION,
            }
        ):
            eligible_strategies.append(strategy)
        else:
            skipped_strategies[strategy] = (
                f"decision regime {regime.value} is outside {strategy.value} eligibility"
            )
    return tuple(eligible_strategies), skipped_strategies
