"""Strategy generation orchestration without regime pre-filtering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType

from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.applicability import (
    StrategyApplicability,
    build_strategy_applicability,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate
from apex.strategies.diagnostics import (
    StrategyDiagnostic,
    build_strategy_diagnostics,
    has_higher_timeframe_breakout,
)
from apex.strategies.entry_status import EntryStatus
from apex.strategies.registry import STRATEGY_REGISTRY, run_strategy_generator
from apex.strategies.strategy_types import StrategyType
from apex.structure.regime import MarketRegime, classify_market_regime


@dataclass(frozen=True, slots=True)
class SuppressedStrategyCandidate:
    """Generated candidate retained for audit but excluded downstream."""

    candidate: TradeCandidate
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("suppressed candidate reason codes cannot be empty")
        if not self.reasons:
            raise ValueError("suppressed candidate reasons cannot be empty")


@dataclass(frozen=True, slots=True)
class CandidateActionability:
    """Discovery status attached to one raw strategy candidate."""

    candidate: TradeCandidate
    status: EntryStatus


@dataclass(frozen=True, slots=True)
class StrategyAnalysisResult:
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
    strategy_applicability: Mapping[StrategyType, StrategyApplicability] | None = None
    candidate_actionability: tuple[CandidateActionability, ...] = ()
    suppressed_candidates: tuple[SuppressedStrategyCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("analysis-result symbol cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("analysis decision time must be timezone-aware")
        if not self.evaluated_strategies:
            raise ValueError("at least one evaluated strategy is required")
        if len(set(self.evaluated_strategies)) != len(self.evaluated_strategies):
            raise ValueError("evaluated strategies must be unique")

        eligible = self.eligible_strategies or self.evaluated_strategies
        if len(set(eligible)) != len(eligible):
            raise ValueError("eligible strategies must be unique")
        if any(strategy not in self.evaluated_strategies for strategy in eligible):
            raise ValueError("eligible strategies must be evaluated")

        skipped = dict(self.skipped_strategies or {})
        if any(strategy not in self.evaluated_strategies for strategy in skipped):
            raise ValueError("skipped strategies must be evaluated")
        if any(strategy in eligible for strategy in skipped):
            raise ValueError("strategy cannot be both eligible and skipped")

        diagnostics = dict(self.strategy_diagnostics or {})
        applicability = dict(self.strategy_applicability or {})
        if applicability and set(applicability) != set(self.evaluated_strategies):
            raise ValueError("strategy applicability must cover every strategy")

        all_candidates = (
            *self.candidates,
            *(entry.candidate for entry in self.suppressed_candidates),
        )
        for item in all_candidates:
            if item.symbol != self.symbol:
                raise ValueError("candidate symbol must match analysis symbol")
            if item.decision_time != self.decision_time:
                raise ValueError("candidate decision time must match analysis decision time")
            if StrategyType(item.strategy.value) not in self.evaluated_strategies:
                raise ValueError("candidate strategy must be evaluated")

        order = self.evaluated_strategies.index
        strategies = tuple(StrategyType(item.strategy.value) for item in self.candidates)
        if strategies != tuple(sorted(strategies, key=order)):
            raise ValueError("candidates must preserve stable registry ordering")

        actionability = self.candidate_actionability or tuple(
            CandidateActionability(
                candidate=candidate,
                status=classify_candidate_actionability(candidate),
            )
            for candidate in self.candidates
        )
        if tuple(entry.candidate for entry in actionability) != self.candidates:
            raise ValueError("candidate actionability must align one-to-one with candidates")

        object.__setattr__(self, "eligible_strategies", eligible)
        object.__setattr__(self, "skipped_strategies", MappingProxyType(skipped))
        object.__setattr__(self, "strategy_diagnostics", MappingProxyType(diagnostics))
        object.__setattr__(self, "strategy_applicability", MappingProxyType(applicability))
        object.__setattr__(self, "candidate_actionability", actionability)


def analyze_strategies(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> StrategyAnalysisResult:
    """Run every registered generator and retain all valid candidates."""

    evaluated = tuple(strategy for strategy, _generator in STRATEGY_REGISTRY)
    decision_regime = classify_market_regime(context.decision_frame.structure)
    higher_breakout = has_higher_timeframe_breakout(context)
    candidates = tuple(
        _normalize_candidate(candidate)
        for _strategy, generator in STRATEGY_REGISTRY
        for candidate in run_strategy_generator(
            generator,
            context,
            decision_time=decision_time,
        )
    )
    diagnostics = build_strategy_diagnostics(
        context,
        evaluated=evaluated,
        eligible=evaluated,
        skipped={},
        candidates=candidates,
    )
    applicability = build_strategy_applicability(
        regime=decision_regime,
        evaluated=evaluated,
        eligible=evaluated,
        higher_timeframe_breakout=higher_breakout,
    )
    actionability = tuple(
        CandidateActionability(
            candidate=candidate,
            status=classify_candidate_actionability(candidate),
        )
        for candidate in candidates
    )
    return StrategyAnalysisResult(
        symbol=context.symbol,
        decision_time=decision_time,
        candidates=candidates,
        evaluated_strategies=evaluated,
        eligible_strategies=evaluated,
        skipped_strategies={},
        strategy_diagnostics=diagnostics,
        decision_regime=decision_regime,
        higher_timeframe_breakout=higher_breakout,
        strategy_applicability=applicability,
        candidate_actionability=actionability,
    )


def _normalize_candidate(candidate: TradeCandidate) -> TradeCandidate:
    return replace(candidate, strategy=StrategyType(candidate.strategy.value))
