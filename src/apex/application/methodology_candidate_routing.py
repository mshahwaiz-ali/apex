"""Apply methodology strategy decisions to generated candidates before ranking."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_candidate_geometry_safety import (
    DEFAULT_GEOMETRY_SAFETY_POLICY,
    CandidateGeometrySafetyAudit,
    audit_candidate_geometry_safety,
    candidate_geometry_safety_audit_payload,
)
from apex.application.methodology_candidate_lane_horizon import (
    measure_candidate_lane_horizon,
)
from apex.application.methodology_geometry_runtime import GeometryRuntimeContext
from apex.application.methodology_geometry_safety import GeometrySafetyPolicy
from apex.application.methodology_htf_consequences import (
    DEFAULT_HTF_CONSEQUENCE_POLICY,
    HtfConsequence,
    HtfConsequencePolicy,
    apply_htf_consequences,
)
from apex.application.methodology_lane_horizon import LaneHorizonAssessment
from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
    infer_candidate_methodology_context,
)
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
    derive_strategy_enforcement,
    strategy_enforcement_payload,
)
from apex.application.methodology_strategy_evaluation import evaluate_strategy_eligibility
from apex.domain.methodology_contracts import (
    LayeredStateSnapshot,
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.domain.methodology_htf_relationship import HtfRelationshipAssessment
from apex.strategies.analysis import StrategyAnalysisResult, SuppressedStrategyCandidate
from apex.strategies.candidate_identity import candidate_identities
from apex.strategies.contracts import TradeCandidate
from apex.strategies.entry_status import EntryStatus
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


def _candidate_lane_horizon_assessment(
    candidate: TradeCandidate,
    *,
    entry_status: EntryStatus,
) -> LaneHorizonAssessment | None:
    """Return a measurable assessment when complete inputs are available.

    AttributeError is treated as unavailable so lightweight test doubles and
    legacy callers retain the previous inference path. Real candidate
    validation errors are not swallowed.
    """

    try:
        metadata = candidate.metadata
    except AttributeError:
        return None

    runner_authority_value = metadata.get("runner_authority")
    runner_authority = runner_authority_value if isinstance(runner_authority_value, bool) else None
    measurement = measure_candidate_lane_horizon(
        candidate,
        entry_status=entry_status,
        runner_authority=runner_authority,
    )
    return measurement.assessment


_DEFAULT_LAYERED_STATE = LayeredStateSnapshot()


def _candidate_layered_state(
    candidate: TradeCandidate,
) -> LayeredStateSnapshot | None:
    try:
        layered_state = candidate.layered_state
    except AttributeError:
        return None
    return None if layered_state == _DEFAULT_LAYERED_STATE else layered_state


def _htf_assessment_from_layered_state(
    layered_state: LayeredStateSnapshot | None,
) -> HtfRelationshipAssessment | None:
    if layered_state is None:
        return None

    relationship = layered_state.timeframe_relationship
    severity = layered_state.relationship_severity
    if (
        relationship is TimeframeRelationship.UNAVAILABLE
        or severity is RelationshipSeverity.UNAVAILABLE
    ):
        return None

    if relationship is TimeframeRelationship.WITH_TREND:
        return HtfRelationshipAssessment(
            relationship=relationship,
            severity=severity,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_required=False,
            hard_reject=False,
            reasons=("trade direction aligns with higher-timeframe structure",),
        )
    if relationship is TimeframeRelationship.MIXED:
        mild = severity is RelationshipSeverity.MILD
        return HtfRelationshipAssessment(
            relationship=relationship,
            severity=severity,
            runner_allowed=False,
            confirmation_required=not mild,
            target_ceiling_required=True,
            hard_reject=False,
            reasons=(
                "higher-timeframe relationship is mixed and requires constrained target authority",
            ),
        )
    if relationship is TimeframeRelationship.COUNTERTREND_SCALP:
        return HtfRelationshipAssessment(
            relationship=relationship,
            severity=severity,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_required=True,
            hard_reject=False,
            reasons=(
                "trade opposes confirmed higher-timeframe continuation; "
                "scalp-only treatment required",
            ),
        )
    if relationship is TimeframeRelationship.REVERSAL_ATTEMPT:
        return HtfRelationshipAssessment(
            relationship=relationship,
            severity=severity,
            runner_allowed=False,
            confirmation_required=True,
            target_ceiling_required=True,
            hard_reject=False,
            reasons=("trade depends on an unconfirmed higher-timeframe reversal attempt",),
        )
    if relationship is TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED:
        return HtfRelationshipAssessment(
            relationship=relationship,
            severity=severity,
            runner_allowed=True,
            confirmation_required=False,
            target_ceiling_required=False,
            hard_reject=False,
            reasons=("higher-timeframe structural reversal is confirmed",),
        )
    return HtfRelationshipAssessment(
        relationship=relationship,
        severity=severity,
        runner_allowed=False,
        confirmation_required=True,
        target_ceiling_required=True,
        hard_reject=True,
        reasons=("nearby opposing higher-timeframe structure destroys usable reward space",),
    )


def _candidate_htf_consequence(
    layered_state: LayeredStateSnapshot | None,
    *,
    lane: OpportunityLane | None,
    holding_horizon: HoldingHorizon | None,
    policy: HtfConsequencePolicy,
) -> HtfConsequence | None:
    assessment = _htf_assessment_from_layered_state(layered_state)
    if assessment is None:
        return None
    return apply_htf_consequences(
        assessment,
        lane=lane,
        holding_horizon=holding_horizon,
        policy=policy,
    )


@dataclass(frozen=True, slots=True)
class GeometrySafetyCoverage:
    """Aggregate shadow-audit coverage without affecting eligibility."""

    candidate_count: int
    available_count: int
    unavailable_count: int
    pass_count: int
    reject_count: int
    incomplete_count: int
    missing_measurement_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        counts = (
            self.candidate_count,
            self.available_count,
            self.unavailable_count,
            self.pass_count,
            self.reject_count,
            self.incomplete_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("geometry coverage counts cannot be negative")
        if self.available_count + self.unavailable_count != self.candidate_count:
            raise ValueError("geometry coverage availability counts must balance")
        if self.pass_count + self.reject_count + self.incomplete_count != self.available_count:
            raise ValueError("geometry coverage state counts must balance")


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
    geometry_safety_audits: tuple[CandidateGeometrySafetyAudit, ...] = ()

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
        decision_keys = tuple((item.strategy, item.candidate_id) for item in self.decisions)
        if len(set(decision_keys)) != len(decision_keys):
            raise ValueError(
                "methodology candidate decisions must be unique by strategy and candidate"
            )
        if not self.reason_codes:
            raise ValueError("methodology candidate routing requires reason codes")


def evaluate_methodology_candidate_routing(
    analysis: StrategyAnalysisResult,
    *,
    market_state: PrimaryMarketState | None,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
    geometry_runtime_context: GeometryRuntimeContext | None = None,
    geometry_safety_policy: GeometrySafetyPolicy = DEFAULT_GEOMETRY_SAFETY_POLICY,
    htf_consequence_policy: HtfConsequencePolicy = DEFAULT_HTF_CONSEQUENCE_POLICY,
) -> MethodologyCandidateRoutingResult:
    """Evaluate each generated strategy from its own candidate evidence."""

    decisions: list[StrategyEnforcementDecision] = []
    geometry_safety_audits: list[CandidateGeometrySafetyAudit] = []
    identities = candidate_identities(analysis.candidates)
    identity_by_object = dict(zip(map(id, analysis.candidates), identities, strict=True))
    status_by_object = {
        id(item.candidate): item.status for item in analysis.candidate_actionability
    }
    for strategy in analysis.evaluated_strategies:
        strategy_candidates = tuple(
            candidate
            for candidate in analysis.candidates
            if StrategyType(candidate.strategy.value) is strategy
        )
        if not strategy_candidates:
            decisions.append(
                derive_strategy_enforcement(
                    evaluate_strategy_eligibility(
                        strategy,
                        market_state=market_state,
                    )
                )
            )
            continue
        for candidate in strategy_candidates:
            entry_status = status_by_object[id(candidate)]
            lane_horizon = _candidate_lane_horizon_assessment(
                candidate,
                entry_status=entry_status,
            )
            context = infer_candidate_methodology_context(
                candidate,
                entry_status=entry_status,
                lane_horizon=lane_horizon,
            )
            candidate_id = identity_by_object[id(candidate)]
            layered_state = _candidate_layered_state(candidate)
            htf_consequence = _candidate_htf_consequence(
                layered_state,
                lane=context.lane,
                holding_horizon=context.holding_horizon,
                policy=htf_consequence_policy,
            )
            geometry_safety_audits.append(
                audit_candidate_geometry_safety(
                    candidate,
                    candidate_id=candidate_id,
                    lane=context.lane,
                    policy=geometry_safety_policy,
                    runtime_context=geometry_runtime_context,
                )
            )
            decisions.append(
                derive_strategy_enforcement(
                    evaluate_strategy_eligibility(
                        strategy,
                        market_state=market_state,
                        evidence=strategy_evidence_observations(candidate.evidence),
                        lane=context.lane,
                        direction=candidate.direction,
                        holding_horizon=context.holding_horizon,
                        layered_state=layered_state,
                        htf_consequence=htf_consequence,
                    ),
                    candidate_id=candidate_id,
                )
            )
    return apply_methodology_candidate_routing(
        analysis,
        tuple(decisions),
        mode=mode,
        geometry_safety_audits=tuple(geometry_safety_audits),
    )


def apply_methodology_candidate_routing(
    analysis: StrategyAnalysisResult,
    decisions: tuple[StrategyEnforcementDecision, ...],
    *,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
    geometry_safety_audits: tuple[CandidateGeometrySafetyAudit, ...] = (),
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
            geometry_safety_audits=geometry_safety_audits,
        )

    identities = candidate_identities(analysis.candidates)
    identity_by_object = dict(zip(map(id, analysis.candidates), identities, strict=True))
    decision_by_candidate = {
        item.candidate_id: item for item in decisions if item.candidate_id is not None
    }
    decision_by_strategy = {item.strategy: item for item in decisions if item.candidate_id is None}
    status_by_object = {
        id(item.candidate): item.status for item in analysis.candidate_actionability
    }
    retained: list[TradeCandidate] = []
    newly_suppressed: list[SuppressedStrategyCandidate] = []
    suppressed_strategies: list[StrategyType] = []
    for candidate in analysis.candidates:
        strategy = StrategyType(candidate.strategy.value)
        decision = decision_by_candidate.get(
            identity_by_object[id(candidate)],
            decision_by_strategy.get(strategy),
        )
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
        geometry_safety_audits=geometry_safety_audits,
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


def geometry_safety_coverage(
    audits: tuple[CandidateGeometrySafetyAudit, ...],
) -> GeometrySafetyCoverage:
    """Summarize shadow geometry availability and states."""

    missing: dict[str, int] = {}
    available = 0
    passed = 0
    rejected = 0
    incomplete = 0
    for audit in audits:
        for measurement in audit.missing_measurements:
            missing[measurement] = missing.get(measurement, 0) + 1
        assessment = audit.assessment
        if assessment is None:
            continue
        available += 1
        state = assessment.state.value
        if state == "pass":
            passed += 1
        elif state == "reject":
            rejected += 1
        else:
            incomplete += 1

    return GeometrySafetyCoverage(
        candidate_count=len(audits),
        available_count=available,
        unavailable_count=len(audits) - available,
        pass_count=passed,
        reject_count=rejected,
        incomplete_count=incomplete,
        missing_measurement_counts=tuple(sorted(missing.items())),
    )


def methodology_candidate_routing_payload(
    result: MethodologyCandidateRoutingResult,
) -> dict[str, object]:
    """Serialize routing decisions and suppressed candidates for audit."""

    coverage = geometry_safety_coverage(result.geometry_safety_audits)
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
        "geometry_safety_coverage": {
            "candidate_count": coverage.candidate_count,
            "available_count": coverage.available_count,
            "unavailable_count": coverage.unavailable_count,
            "pass_count": coverage.pass_count,
            "reject_count": coverage.reject_count,
            "incomplete_count": coverage.incomplete_count,
            "missing_measurement_counts": dict(coverage.missing_measurement_counts),
            "enforcement_ready": (
                coverage.candidate_count > 0
                and coverage.unavailable_count == 0
                and coverage.incomplete_count == 0
            ),
        },
        "geometry_safety_audits": [
            candidate_geometry_safety_audit_payload(item) for item in result.geometry_safety_audits
        ],
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
    "GeometrySafetyCoverage",
    "MethodologyCandidateRoutingResult",
    "MethodologyRoutingParityAudit",
    "apply_methodology_candidate_routing",
    "evaluate_methodology_candidate_routing",
    "evaluate_methodology_routing_parity",
    "geometry_safety_coverage",
    "methodology_candidate_routing_payload",
    "methodology_routing_parity_payload",
]
