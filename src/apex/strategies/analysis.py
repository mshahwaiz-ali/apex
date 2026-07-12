"""Phase 4 strategy-candidate orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyType, TradeCandidate
from apex.strategies.registry import STRATEGY_REGISTRY, run_strategy_generator


@dataclass(frozen=True, slots=True)
class Phase4AnalysisResult:
    """Immutable collection of raw candidates produced in registry order."""

    symbol: str
    decision_time: datetime
    candidates: tuple[TradeCandidate, ...]
    evaluated_strategies: tuple[StrategyType, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("analysis-result symbol cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("analysis decision time must be timezone-aware")
        if not self.evaluated_strategies:
            raise ValueError("at least one evaluated strategy is required")
        if len(set(self.evaluated_strategies)) != len(self.evaluated_strategies):
            raise ValueError("evaluated strategies must be unique")

        for candidate in self.candidates:
            if candidate.symbol != self.symbol:
                raise ValueError("candidate symbol must match the analysis symbol")
            if candidate.decision_time != self.decision_time:
                raise ValueError("candidate decision time must match the analysis decision time")
            if candidate.strategy not in self.evaluated_strategies:
                raise ValueError("candidate strategy must be present in evaluated strategies")

        candidate_strategies = tuple(item.strategy for item in self.candidates)
        expected_order = tuple(
            sorted(candidate_strategies, key=self.evaluated_strategies.index)
        )
        if candidate_strategies != expected_order:
            raise ValueError("candidates must preserve stable registry ordering")


def analyze_phase4(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> Phase4AnalysisResult:
    """Run all candidate generators without ranking or selecting a winning trade."""

    evaluated = tuple(strategy for strategy, _generator in STRATEGY_REGISTRY)
    candidates = tuple(
        candidate
        for _strategy, generator in STRATEGY_REGISTRY
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
    )
