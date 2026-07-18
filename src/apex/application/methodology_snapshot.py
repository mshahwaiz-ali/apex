"""Aggregate canonical methodology state for one analyzed candidate or symbol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import (
    MarketUsabilityAssessment,
    market_usability_payload,
)
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
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    MarketStateClassification,
    SetupMaturity,
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
    duration: DurationExpectation | None = None
    confidence: ConfidenceAssessment | None = None
    rejections: tuple[RejectionReason, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("methodology evidence must not contain duplicates")
        if len(set(self.contradictions)) != len(self.contradictions):
            raise ValueError("methodology contradictions must not contain duplicates")
        if len(set(self.entry_opportunities)) != len(self.entry_opportunities):
            raise ValueError("entry opportunities must not contain duplicates")
        if self.selected_entry is not None:
            if self.selected_entry.opportunity not in self.entry_opportunities:
                raise ValueError(
                    "selected entry must reference an opportunity in the canonical set"
                )
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("target candidates must not contain duplicates")
        if len(set(self.rejections)) != len(self.rejections):
            raise ValueError("rejection reasons must not contain duplicates")
        self._validate_directional_geometry()

    def _validate_directional_geometry(self) -> None:
        if self.direction is None or self.selected_entry is None:
            return
        entry = self.selected_entry.opportunity
        if self.invalidation is not None:
            if self.direction is TradeDirection.LONG and self.invalidation.price >= entry.zone_low:
                raise ValueError("long invalidation must be below the selected entry zone")
            if self.direction is TradeDirection.SHORT and self.invalidation.price <= entry.zone_high:
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
        return (
            not self.hard_blockers
            and self.direction is not None
            and self.selected_entry is not None
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
            None
            if snapshot.confirmation_policy is None
            else snapshot.confirmation_policy.value
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
            "opportunity": _entry_opportunity_payload(
                snapshot.selected_entry.opportunity
            ),
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
