"""Apply methodology strategy decisions to generated candidates before ranking."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
    derive_strategy_enforcement,
)
from apex.application.methodology_strategy_evaluation import evaluate_strategy_eligibility
from apex.strategies.analysis import StrategyAnalysisResult, SuppressedStrategyCandidate
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True, slots=True)
class MethodologyCandidateRoutingResult:
    """Candidate-routing outcome with deterministic audit metadata."""

    analysis: StrategyAnalysisResult
    mode: MethodologyGateMode
    suppressed_candidate_count: int
    suppressed_strategies: tuple[StrategyType, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.suppressed_candidate_count < 0:
            raise ValueError("suppressed candidate count cannot be negative")
        if len(set(self.suppressed_strategies)) != len(self.suppressed_strategies):
            raise ValueError("suppressed strategies must be unique")
        if not self.reason_codes:
            raise ValueError("methodology candidate routing requires reason codes")


def evaluate_methodology_candidate_routing(
    analysis: StrategyAnalysisResult,
    *,
    market_state: PrimaryMarketState | None,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
) -> MethodologyCandidateRoutingResult:
    """Evaluate each generated strategy from its own candidate evidence."""

    decisions: list[StrategyEnforcementDecision] = []
    for strategy in analysis.evaluated_strategies:
        evidence = tuple(
            observation
            for candidate in analysis.candidates
            if StrategyType(candidate.strategy.value) is strategy
            for observation in strategy_evidence_observations(candidate.evidence)
        )
        decisions.append(
            derive_strategy_enforcement(
                evaluate_strategy_eligibility(
                    strategy,
                    market_state=market_state,
                    evidence=evidence,
                )
            )
        )
    return apply_methodology_candidate_routing(
        analysis,
        tuple(decisions),
        mode=mode,
    )


def apply_methodology_candidate_routing(
    analysis: StrategyAnalysisResult,
    decisions: tuple[StrategyEnforcementDecision, ...],
    *,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
) -> MethodologyCandidateRoutingResult:
    """Suppress explicit strategy conflicts before ranking when enforcement is enabled.

    Shadow mode preserves every generated candidate. Enforcement mode removes only
    candidates whose strategy has an explicit SUPPRESS decision. Missing decisions,
    deferred metadata, and allowed decisions remain eligible.
    """

    normalized_mode = MethodologyGateMode(mode)
    if normalized_mode is MethodologyGateMode.SHADOW:
        return MethodologyCandidateRoutingResult(
            analysis=analysis,
            mode=normalized_mode,
            suppressed_candidate_count=0,
            suppressed_strategies=(),
            reason_codes=("METHODOLOGY_CANDIDATE_ROUTING_SHADOW",),
        )

    decision_by_strategy = {item.strategy: item for item in decisions}
    retained = []
    newly_suppressed: list[SuppressedStrategyCandidate] = []
    suppressed_strategies: list[StrategyType] = []
    for candidate in analysis.candidates:
        strategy = StrategyType(candidate.strategy.value)
        decision = decision_by_strategy.get(strategy)
        if decision is None or decision.action is not StrategyEnforcementAction.SUPPRESS:
            retained.append(candidate)
            continue
        newly_suppressed.append(
            SuppressedStrategyCandidate(
                candidate=candidate,
                reason_codes=decision.reason_codes,
                reasons=decision.reasons,
            )
        )
        if strategy not in suppressed_strategies:
            suppressed_strategies.append(strategy)

    retained_tuple = tuple(retained)
    retained_ids = {candidate.candidate_id for candidate in retained_tuple}
    routed = replace(
        analysis,
        candidates=retained_tuple,
        candidate_actionability=tuple(
            item
            for item in analysis.candidate_actionability
            if item.candidate.candidate_id in retained_ids
        ),
        suppressed_candidates=analysis.suppressed_candidates + tuple(newly_suppressed),
    )
    return MethodologyCandidateRoutingResult(
        analysis=routed,
        mode=normalized_mode,
        suppressed_candidate_count=len(newly_suppressed),
        suppressed_strategies=tuple(suppressed_strategies),
        reason_codes=(
            "METHODOLOGY_CANDIDATES_SUPPRESSED"
            if newly_suppressed
            else "METHODOLOGY_CANDIDATE_ROUTING_NO_CHANGE",
        ),
    )


def methodology_candidate_routing_payload(
    result: MethodologyCandidateRoutingResult,
) -> dict[str, object]:
    return {
        "mode": result.mode.value,
        "suppressed_candidate_count": result.suppressed_candidate_count,
        "suppressed_strategies": [item.value for item in result.suppressed_strategies],
        "reason_codes": list(result.reason_codes),
    }


__all__ = [
    "MethodologyCandidateRoutingResult",
    "apply_methodology_candidate_routing",
    "evaluate_methodology_candidate_routing",
    "methodology_candidate_routing_payload",
]
