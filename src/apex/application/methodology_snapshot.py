"""Aggregate canonical methodology state for one analyzed candidate or symbol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import (
    MarketUsabilityAssessment,
    market_usability_payload,
)
from apex.application.methodology_calibration_contracts import CalibrationProvenance
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    Contradiction,
    DurationExpectation,
    EntryOpportunity,
    EvidenceObservation,
    RejectionReason,
    RejectionSeverity,
    StructuralInvalidation,
    TargetCandidate,
)
from apex.application.methodology_evidence_aggregation import (
    aggregate_evidence_families,
    evidence_family_aggregate_payload,
)
from apex.application.methodology_management_contracts import (
    ManagementActionType,
    ManagementStep,
)
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    MarketStateClassification,
    SetupMaturity,
)
from apex.application.methodology_target_context_contracts import (
    ExecutionCostEstimate,
    TargetObstacleEvidence,
)
from apex.strategies.contracts import TradeDirection


@dataclass(frozen=True, slots=True)
class MethodologySnapshot:
    """Normalized methodology result that later phases can populate incrementally."""

    direction: TradeDirection | None = None
    market_usability: MarketUsabilityAssessment | None = None
    market_state: MarketStateClassification | None = None
    setup_maturity: SetupMaturity | None = None
    confirmation_policy: ConfirmationPolicy | None = None
    evidence: tuple[EvidenceObservation, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    entry_opportunities: tuple[EntryOpportunity, ...] = ()
    selected_entry: SelectedEntryDecision | None = None
    invalidation: StructuralInvalidation | None = None
    targets: tuple[TargetCandidate, ...] = ()
    target_obstacles: tuple[TargetObstacleEvidence, ...] = ()
    execution_costs: ExecutionCostEstimate | None = None
    management_steps: tuple[ManagementStep, ...] = ()
    duration: DurationExpectation | None = None
    confidence: ConfidenceAssessment | None = None
    calibration: CalibrationProvenance | None = None
    rejections: tuple[RejectionReason, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("methodology evidence must not contain duplicates")
        if len(set(self.contradictions)) != len(self.contradictions):
            raise ValueError("methodology contradictions must not contain duplicates")
        if len(set(self.entry_opportunities)) != len(self.entry_opportunities):
            raise ValueError("entry opportunities must not contain duplicates")
        if (
            self.selected_entry is not None
            and self.selected_entry.opportunity not in self.entry_opportunities
        ):
            raise ValueError("selected entry must reference an opportunity in the canonical set")
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("target candidates must not contain duplicates")
        if len(set(self.target_obstacles)) != len(self.target_obstacles):
            raise ValueError("target obstacle evidence must not contain duplicates")
        if len(set(self.management_steps)) != len(self.management_steps):
            raise ValueError("management steps must not contain duplicates")
        if len(set(self.rejections)) != len(self.rejections):
            raise ValueError("rejection reasons must not contain duplicates")
        self._validate_target_obstacles()
        self._validate_management_steps()
        self._validate_directional_geometry()

    def _validate_target_obstacles(self) -> None:
        target_roles = {target.role for target in self.targets}
        obstacle_roles = [item.target_role for item in self.target_obstacles]
        if len(set(obstacle_roles)) != len(obstacle_roles):
            raise ValueError("target obstacle roles must be unique")
        if any(role not in target_roles for role in obstacle_roles):
            raise ValueError("target obstacle evidence must reference a canonical target role")

    def _validate_management_steps(self) -> None:
        target_roles = {target.role for target in self.targets}
        partial_total = 0.0
        for step in self.management_steps:
            if step.kind is not ManagementActionType.PARTIAL_EXIT:
                continue
            if step.target_role not in target_roles:
                raise ValueError("partial-exit management must reference a canonical target role")
            partial_total += step.close_percentage or 0.0
        if partial_total > 100.0:
            raise ValueError("partial-exit close percentages cannot exceed 100")

    def _validate_directional_geometry(self) -> None:
        if self.direction is None or self.selected_entry is None:
            return
        entry = self.selected_entry.opportunity
        if self.invalidation is not None:
            if self.direction is TradeDirection.LONG and self.invalidation.price >= entry.zone_low:
                raise ValueError("long invalidation must be below the selected entry zone")
            if (
                self.direction is TradeDirection.SHORT
                and self.invalidation.price <= entry.zone_high
            ):
                raise ValueError("short invalidation must be above the selected entry zone")
        if self.direction is TradeDirection.LONG:
            if any(target.price <= entry.zone_high for target in self.targets):
                raise ValueError("long targets must be above the selected entry zone")
        elif any(target.price >= entry.zone_low for target in self.targets):
            raise ValueError("short targets must be below the selected entry zone")

    @property
    def hard_blockers(self) -> tuple[RejectionReason, ...]:
        return tuple(
            reason
            for reason in self.rejections
            if reason.severity is RejectionSeverity.HARD_BLOCKER
        )

    @property
    def soft_penalties(self) -> tuple[RejectionReason, ...]:
        return tuple(
            reason
            for reason in self.rejections
            if reason.severity is RejectionSeverity.SOFT_PENALTY
        )

    @property
    def executable(self) -> bool:
        entry_available = self.selected_entry is not None or len(self.entry_opportunities) == 1
        return (
            not self.hard_blockers
            and entry_available
            and self.invalidation is not None
            and bool(self.targets)
        )


def methodology_snapshot_payload(snapshot: MethodologySnapshot) -> dict[str, Any]:
    """Serialize a methodology snapshot without implying calibrated probability."""
    evidence_summary = aggregate_evidence_families(snapshot.evidence)
    return {
        "direction": None if snapshot.direction is None else snapshot.direction.value,
        "market_usability": (
            None
            if snapshot.market_usability is None
            else market_usability_payload(snapshot.market_usability)
        ),
        "market_state": None
        if snapshot.market_state is None
        else {
            "primary": snapshot.market_state.primary.value,
            "secondary": [item.value for item in snapshot.market_state.secondary],
            "evidence_ids": list(snapshot.market_state.evidence_ids),
            "reason": snapshot.market_state.reason,
        },
        "setup_maturity": (
            None if snapshot.setup_maturity is None else snapshot.setup_maturity.value
        ),
        "confirmation_policy": (
            None if snapshot.confirmation_policy is None else snapshot.confirmation_policy.value
        ),
        "evidence": [
            {
                "family": item.family.value,
                "source": item.source,
                "normalized_strength": item.normalized_strength,
                "freshness": item.freshness,
                "independence_group": item.independence_group,
                "effect": item.effect.value,
                "reason": item.reason,
            }
            for item in snapshot.evidence
        ],
        "evidence_family_summary": [
            evidence_family_aggregate_payload(item) for item in evidence_summary
        ],
        "contradictions": [
            {
                "code": item.code,
                "family": item.family.value,
                "severity": item.severity,
                "reason": item.reason,
            }
            for item in snapshot.contradictions
        ],
        "entry_opportunities": [
            _entry_opportunity_payload(item) for item in snapshot.entry_opportunities
        ],
        "selected_entry": None
        if snapshot.selected_entry is None
        else {
            "opportunity": _entry_opportunity_payload(snapshot.selected_entry.opportunity),
            "reason": snapshot.selected_entry.reason,
        },
        "invalidation": None
        if snapshot.invalidation is None
        else {
            "price": snapshot.invalidation.price,
            "rule": snapshot.invalidation.rule.value,
            "structure": snapshot.invalidation.structure,
            "failure_event": snapshot.invalidation.failure_event,
            "volatility_buffer": snapshot.invalidation.volatility_buffer,
            "estimated_slippage": snapshot.invalidation.estimated_slippage,
        },
        "targets": [
            {
                "role": item.role.value,
                "price": item.price,
                "source": item.source,
                "expected_move_percentage": item.expected_move_percentage,
                "risk_multiple": item.risk_multiple,
                "conditional": item.conditional,
            }
            for item in snapshot.targets
        ],
        "target_obstacles": [
            {
                "target_role": item.target_role.value,
                "obstacle_price": item.obstacle_price,
                "structure_kind": item.structure_kind,
                "source": item.source,
                "relation": item.relation.value,
                "clearance_buffer_percentage": item.clearance_buffer_percentage,
            }
            for item in snapshot.target_obstacles
        ],
        "execution_costs": None
        if snapshot.execution_costs is None
        else {
            "entry_fee_percentage": snapshot.execution_costs.entry_fee_percentage,
            "exit_fee_percentage": snapshot.execution_costs.exit_fee_percentage,
            "spread_percentage": snapshot.execution_costs.spread_percentage,
            "entry_slippage_percentage": (snapshot.execution_costs.entry_slippage_percentage),
            "exit_slippage_percentage": snapshot.execution_costs.exit_slippage_percentage,
            "funding_percentage": snapshot.execution_costs.funding_percentage,
            "total_percentage": snapshot.execution_costs.total_percentage,
            "source": snapshot.execution_costs.source,
        },
        "management_steps": [
            {
                "kind": item.kind.value,
                "trigger": item.trigger,
                "action": item.action,
                "rationale": list(item.rationale),
                "target_role": (None if item.target_role is None else item.target_role.value),
                "close_percentage": item.close_percentage,
            }
            for item in snapshot.management_steps
        ],
        "duration": None
        if snapshot.duration is None
        else {
            "category": snapshot.duration.category.value,
            "expected_hold_min_seconds": snapshot.duration.expected_hold_min_seconds,
            "expected_hold_max_seconds": snapshot.duration.expected_hold_max_seconds,
            "expected_bars": snapshot.duration.expected_bars,
            "setup_expiry_bars": snapshot.duration.setup_expiry_bars,
            "expiry_reason": snapshot.duration.expiry_reason,
        },
        "confidence": None
        if snapshot.confidence is None
        else {
            "setup": snapshot.confidence.setup.value,
            "execution": snapshot.confidence.execution.value,
            "target": snapshot.confidence.target.value,
            "data": snapshot.confidence.data.value,
            "historical": snapshot.confidence.historical.value,
            "overall": snapshot.confidence.overall.value,
            "basis": snapshot.confidence.basis.value,
            "strongest_support": snapshot.confidence.strongest_support,
            "strongest_contradiction": snapshot.confidence.strongest_contradiction,
            "missing_evidence": list(snapshot.confidence.missing_evidence),
            "model_estimated_success_rate": snapshot.confidence.model_estimated_success_rate,
            "sample_size": snapshot.confidence.sample_size,
        },
        "calibration": None
        if snapshot.calibration is None
        else {
            "segment_key": snapshot.calibration.segment_key,
            "strategy_version": snapshot.calibration.strategy_version,
            "dataset_id": snapshot.calibration.dataset_id,
            "training_start": snapshot.calibration.training_start.isoformat(),
            "training_end": snapshot.calibration.training_end.isoformat(),
            "validation_start": snapshot.calibration.validation_start.isoformat(),
            "validation_end": snapshot.calibration.validation_end.isoformat(),
            "training_sample_size": snapshot.calibration.training_sample_size,
            "validation_sample_size": snapshot.calibration.validation_sample_size,
            "out_of_sample": snapshot.calibration.out_of_sample,
            "chronological_split": snapshot.calibration.chronological_split,
            "leakage_checks_passed": snapshot.calibration.leakage_checks_passed,
            "costs_included": snapshot.calibration.costs_included,
            "regime_stability_checked": snapshot.calibration.regime_stability_checked,
            "calibration_error": snapshot.calibration.calibration_error,
            "authoritative_probability": snapshot.calibration.authoritative_probability,
        },
        "rejections": [
            {
                "code": item.code.value,
                "severity": item.severity.value,
                "reason": item.reason,
                "penalty": item.penalty,
            }
            for item in snapshot.rejections
        ],
        "hard_blockers": [item.code.value for item in snapshot.hard_blockers],
        "soft_penalties": [item.code.value for item in snapshot.soft_penalties],
        "executable": snapshot.executable,
    }


def _entry_opportunity_payload(opportunity: EntryOpportunity) -> dict[str, Any]:
    return {
        "kind": opportunity.kind.value,
        "zone_low": opportunity.zone_low,
        "zone_high": opportunity.zone_high,
        "ideal_entry": opportunity.ideal_entry,
        "confirmation_level": opportunity.confirmation_level,
        "maximum_chase": opportunity.maximum_chase,
        "current_distance_percentage": opportunity.current_distance_percentage,
        "current_distance_atr": opportunity.current_distance_atr,
        "quality": opportunity.quality,
        "reason": opportunity.reason,
        "expiry_bars": opportunity.expiry_bars,
    }


__all__ = ["MethodologySnapshot", "methodology_snapshot_payload"]
