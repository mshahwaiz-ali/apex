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
    strategy_enforcement_payload,
)
from apex.application.methodology_strategy_evaluation import evaluate_strategy_eligibility
from apex.strategies.analysis import StrategyAnalysisResult, SuppressedStrategyCandidate
from apex.strategies.candidate_identity import candidate_identities
from apex.strategies.contracts import TradeCandidate
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True, slots=True)
class MethodologyRoutingParityAudit:
    """Deterministic preview of what enforcement would change from shadow mode."""

    shadow_candidate_count: int
    enforced_candidate_count: int
    suppressed_candidate_count: int
    suppressed_strategies: tuple[StrategyType, ...]
    would_change_candidate_set: bool
    all_candidates_would_be_suppressed: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("shadow candidate count", self.shadow_candidate_count),
            ("enforced candidate count", self.enforced_candidate_count),
            ("suppressed candidate count", self.suppressed_candidate_count),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.enforced_candidate_count > self.shadow_candidate_count:
            raise ValueError("enforcement cannot increase the candidate count")
        if self.suppressed_candidate_count != (
            self.shadow_candidate_count - self.enforced_candidate_count
        ):
            raise ValueError("suppressed count must equal the shadow/enforce difference")
        if len(set(self.suppressed_strategies)) != len(self.suppressed_strategies):
            raise ValueError("suppressed strategies must be unique")
        if not self.reason_codes:
            raise ValueError("methodology parity audit requires reason codes")


@dataclass(frozen=True, slots=True)
class MethodologyCandidateRoutingResult:
    """Candidate-routing outcome with deterministic audit metadata."""

    analysis: StrategyAnalysisResult
    mode: MethodologyGateMode
    decisions: tuple[StrategyEnforcementDecision, ...]
    input_candidate_count: int
    suppressed_candidate_count: int
    suppressed_strategies: tuple[StrategyType, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.input_candidate_count < 0:
            raise ValueError("input candidate count cannot be negative")
        if self.suppressed_candidate_count < 0:
            raise ValueError("suppressed candidate count cannot be negative")
        if (
            len(self.analysis.candidates) + self.suppressed_candidate_count
            != self.input_candidate_count
        ):
            raise ValueError(
                "methodology routing must balance input candidates into retained and suppressed"
            )
        if len(set(self.suppressed_strategies)) != len(self.suppressed_strategies):
            raise ValueError("suppressed strategies must be unique")
        if len({item.strategy for item in self.decisions}) != len(self.decisions):
            raise ValueError("methodology candidate decisions must be unique by strategy")
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
            decisions=decisions,
            input_candidate_count=len(analysis.candidates),
            suppressed_candidate_count=0,
            suppressed_strategies=(),
            reason_codes=("METHODOLOGY_CANDIDATE_ROUTING_SHADOW",),
        )

    decision_by_strategy = {item.strategy: item for item in decisions}
    identities = candidate_identities(analysis.candidates)
    identity_by_object = dict(zip(map(id, analysis.candidates), identities, strict=True))
    status_by_object = {
        id(item.candidate): item.status for item in analysis.candidate_actionability
    }
    retained: list[TradeCandidate] = []
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
                candidate_id=identity_by_object[id(candidate)],
                entry_status=status_by_object.get(id(candidate)),
                suppression_stage="methodology_enforcement",
            )
        )
        if strategy not in suppressed_strategies:
            suppressed_strategies.append(strategy)

    retained_tuple = tuple(retained)
    retained_identity = {id(candidate) for candidate in retained_tuple}
    routed = replace(
        analysis,
        candidates=retained_tuple,
        candidate_actionability=tuple(
            item
            for item in analysis.candidate_actionability
            if id(item.candidate) in retained_identity
        ),
        suppressed_candidates=analysis.suppressed_candidates + tuple(newly_suppressed),
    )
    return MethodologyCandidateRoutingResult(
        analysis=routed,
        mode=normalized_mode,
        decisions=decisions,
        input_candidate_count=len(analysis.candidates),
        suppressed_candidate_count=len(newly_suppressed),
        suppressed_strategies=tuple(suppressed_strategies),
        reason_codes=(
            "METHODOLOGY_CANDIDATES_SUPPRESSED"
            if newly_suppressed
            else "METHODOLOGY_CANDIDATE_ROUTING_NO_CHANGE",
        ),
    )


def evaluate_methodology_routing_parity(
    analysis: StrategyAnalysisResult,
    decisions: tuple[StrategyEnforcementDecision, ...],
) -> MethodologyRoutingParityAudit:
    """Compare shadow and enforce outcomes without mutating live routing mode."""

    shadow = apply_methodology_candidate_routing(
        analysis,
        decisions,
        mode=MethodologyGateMode.SHADOW,
    )
    enforced = apply_methodology_candidate_routing(
        analysis,
        decisions,
        mode=MethodologyGateMode.ENFORCE,
    )
    shadow_count = len(shadow.analysis.candidates)
    enforced_count = len(enforced.analysis.candidates)
    suppressed_count = shadow_count - enforced_count
    would_change = suppressed_count > 0
    all_suppressed = shadow_count > 0 and enforced_count == 0
    return MethodologyRoutingParityAudit(
        shadow_candidate_count=shadow_count,
        enforced_candidate_count=enforced_count,
        suppressed_candidate_count=suppressed_count,
        suppressed_strategies=enforced.suppressed_strategies,
        would_change_candidate_set=would_change,
        all_candidates_would_be_suppressed=all_suppressed,
        reason_codes=(
            "METHODOLOGY_ENFORCEMENT_WOULD_CHANGE_CANDIDATES"
            if would_change
            else "METHODOLOGY_ENFORCEMENT_PARITY",
        ),
    )


def methodology_routing_parity_payload(
    audit: MethodologyRoutingParityAudit,
) -> dict[str, object]:
    """Serialize the shadow/enforce candidate-set parity audit."""

    return {
        "shadow_candidate_count": audit.shadow_candidate_count,
        "enforced_candidate_count": audit.enforced_candidate_count,
        "suppressed_candidate_count": audit.suppressed_candidate_count,
        "suppressed_strategies": [item.value for item in audit.suppressed_strategies],
        "would_change_candidate_set": audit.would_change_candidate_set,
        "all_candidates_would_be_suppressed": audit.all_candidates_would_be_suppressed,
        "reason_codes": list(audit.reason_codes),
    }


def methodology_candidate_routing_payload(
    result: MethodologyCandidateRoutingResult,
) -> dict[str, object]:
    """Serialize routing decisions and suppressed candidates for audit."""

    newly_suppressed = (
        result.analysis.suppressed_candidates[-result.suppressed_candidate_count :]
        if result.suppressed_candidate_count
        else ()
    )
    return {
        "mode": result.mode.value,
        "input_candidate_count": result.input_candidate_count,
        "retained_candidate_count": len(result.analysis.candidates),
        "suppressed_candidate_count": result.suppressed_candidate_count,
        "lineage_balanced": (
            result.input_candidate_count
            == len(result.analysis.candidates) + result.suppressed_candidate_count
        ),
        "all_generated_candidates_suppressed": (
            result.suppressed_candidate_count > 0 and not result.analysis.candidates
        ),
        "suppressed_strategies": [item.value for item in result.suppressed_strategies],
        "reason_codes": list(result.reason_codes),
        "strategy_decisions": [strategy_enforcement_payload(item) for item in result.decisions],
        "suppressed_candidates": [
            {
                "candidate_id": item.candidate_id,
                "strategy": item.candidate.strategy.value,
                "direction": item.candidate.direction.value,
                "entry_status": (
                    item.entry_status.value if item.entry_status is not None else None
                ),
                "suppression_stage": item.suppression_stage,
                "terminal_outcome": "suppressed",
                "reason_codes": list(item.reason_codes),
                "reasons": list(item.reasons),
            }
            for item in newly_suppressed
        ],
    }


__all__ = [
    "MethodologyCandidateRoutingResult",
    "MethodologyRoutingParityAudit",
    "apply_methodology_candidate_routing",
    "evaluate_methodology_candidate_routing",
    "evaluate_methodology_routing_parity",
    "methodology_candidate_routing_payload",
    "methodology_routing_parity_payload",
]
