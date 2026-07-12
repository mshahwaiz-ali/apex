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
        if tuple(item.strategy for item in self.candidates) != tuple(
            sorted(
                (item.strategy for item in self.candidates),
                key=self.evaluated_strategies.index,
            )
        ):
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
