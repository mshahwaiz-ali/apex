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
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    MarketStateClassification,
    SetupMaturity,
)


@dataclass(frozen=True, slots=True)
class MethodologySnapshot:
    """Normalized methodology result that later phases can populate incrementally."""

    market_usability: MarketUsabilityAssessment | None = None
    market_state: MarketStateClassification | None = None
    setup_maturity: SetupMaturity | None = None
    confirmation_policy: ConfirmationPolicy | None = None
    evidence: tuple[EvidenceObservation, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    entry_opportunities: tuple[EntryOpportunity, ...] = ()
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
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("target candidates must not contain duplicates")
        if len(set(self.rejections)) != len(self.rejections):
            raise ValueError("rejection reasons must not contain duplicates")

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
            and self.invalidation is not None
            and bool(self.entry_opportunities)
            and bool(self.targets)
        )


def methodology_snapshot_payload(snapshot: MethodologySnapshot) -> dict[str, Any]:
    """Serialize a methodology snapshot without implying calibrated probability."""

    evidence_summary = aggregate_evidence_families(snapshot.evidence)
    return {
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
            {
                "kind": item.kind.value,
                "zone_low": item.zone_low,
                "zone_high": item.zone_high,
                "ideal_entry": item.ideal_entry,
                "confirmation_level": item.confirmation_level,
                "maximum_chase": item.maximum_chase,
                "current_distance_percentage": item.current_distance_percentage,
                "current_distance_atr": item.current_distance_atr,
                "quality": item.quality,
                "reason": item.reason,
                "expiry_bars": item.expiry_bars,
            }
            for item in snapshot.entry_opportunities
        ],
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


__all__ = ["MethodologySnapshot", "methodology_snapshot_payload"]
