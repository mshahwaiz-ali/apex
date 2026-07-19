"""Read-only collision diagnostics for concurrent trade opportunities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeCandidate, TradeDirection


class CollisionKind(StrEnum):
    """Geometric relationship between two candidate entry zones."""

    NONE = "none"
    SAME_DIRECTION_OVERLAP = "same_direction_overlap"
    OPPOSITE_DIRECTION_OVERLAP = "opposite_direction_overlap"


@dataclass(frozen=True, slots=True)
class EntryZoneOverlap:
    """Intersection geometry for two existing entry zones."""

    lower: float | None
    upper: float | None
    width: float
    overlap_ratio: float

    @property
    def overlaps(self) -> bool:
        return self.lower is not None and self.upper is not None


@dataclass(frozen=True, slots=True)
class OpportunityCollisionAudit:
    """Read-only collision result that never mutates either candidate."""

    left_symbol: str
    right_symbol: str
    left_direction: TradeDirection
    right_direction: TradeDirection
    kind: CollisionKind
    overlap: EntryZoneOverlap
    current_price_gap: float
    same_symbol: bool

    @property
    def unresolved_opposite_collision(self) -> bool:
        return self.same_symbol and self.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP


def _entry_width(candidate: TradeCandidate) -> float:
    return candidate.entry.upper - candidate.entry.lower


def audit_cmp_collision(
    left: TradeCandidate,
    right: TradeCandidate,
) -> OpportunityCollisionAudit:
    """Audit entry-zone overlap at current market price without resolution."""

    values = (
        left.entry.lower,
        left.entry.upper,
        left.entry.current_price,
        right.entry.lower,
        right.entry.upper,
        right.entry.current_price,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("collision inputs must be finite")

    overlap_lower = max(left.entry.lower, right.entry.lower)
    overlap_upper = min(left.entry.upper, right.entry.upper)
    overlaps = overlap_lower <= overlap_upper

    if overlaps:
        overlap_width = max(0.0, overlap_upper - overlap_lower)
        denominator = max(min(_entry_width(left), _entry_width(right)), 1e-12)
        overlap_ratio = min(1.0, overlap_width / denominator)
        overlap = EntryZoneOverlap(
            lower=overlap_lower,
            upper=overlap_upper,
            width=overlap_width,
            overlap_ratio=overlap_ratio,
        )
        kind = (
            CollisionKind.SAME_DIRECTION_OVERLAP
            if left.direction is right.direction
            else CollisionKind.OPPOSITE_DIRECTION_OVERLAP
        )
    else:
        overlap = EntryZoneOverlap(
            lower=None,
            upper=None,
            width=0.0,
            overlap_ratio=0.0,
        )
        kind = CollisionKind.NONE

    return OpportunityCollisionAudit(
        left_symbol=left.symbol,
        right_symbol=right.symbol,
        left_direction=left.direction,
        right_direction=right.direction,
        kind=kind,
        overlap=overlap,
        current_price_gap=abs(left.entry.current_price - right.entry.current_price),
        same_symbol=left.symbol == right.symbol,
    )


class CollisionResolution(StrEnum):
    """Diagnostic outcome for an unresolved opposite-direction collision."""

    LEFT = "left"
    RIGHT = "right"
    NEUTRAL = "neutral"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class CollisionResolutionPolicy:
    """Weights and margin used to compare colliding candidates."""

    quality_weight: float = 1.0
    evidence_weight: float = 1.0
    contradiction_penalty_weight: float = 1.0
    minimum_advantage: float = 0.05

    def __post_init__(self) -> None:
        values = (
            self.quality_weight,
            self.evidence_weight,
            self.contradiction_penalty_weight,
            self.minimum_advantage,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("collision-resolution policy values must be finite")
        if self.quality_weight < 0:
            raise ValueError("quality weight cannot be negative")
        if self.evidence_weight < 0:
            raise ValueError("evidence weight cannot be negative")
        if self.contradiction_penalty_weight < 0:
            raise ValueError("contradiction penalty weight cannot be negative")
        if self.minimum_advantage < 0:
            raise ValueError("minimum advantage cannot be negative")


@dataclass(frozen=True, slots=True)
class CollisionCandidateScore:
    """Read-only diagnostic score for one colliding candidate."""

    symbol: str
    direction: TradeDirection
    quality_component: float
    evidence_component: float
    contradiction_penalty: float
    total: float


@dataclass(frozen=True, slots=True)
class CollisionResolutionAudit:
    """Diagnostic comparison that never filters or mutates candidates."""

    collision: OpportunityCollisionAudit
    left: CollisionCandidateScore
    right: CollisionCandidateScore
    advantage: float
    resolution: CollisionResolution

    @property
    def has_decisive_winner(self) -> bool:
        return self.resolution in (
            CollisionResolution.LEFT,
            CollisionResolution.RIGHT,
        )


def _candidate_quality_mean(candidate: TradeCandidate) -> float:
    values = (
        candidate.quality.trend_alignment,
        candidate.quality.structure_quality,
        candidate.quality.entry_quality,
        candidate.quality.momentum_quality,
        candidate.quality.volume_quality,
        candidate.quality.liquidity_quality,
        candidate.quality.target_space_quality,
    )
    return sum(values) / len(values)


def _candidate_evidence_strength(candidate: TradeCandidate) -> float:
    positive = (
        len(candidate.evidence.supporting)
        + len(candidate.evidence.feature_references)
        + len(candidate.evidence.structure_references)
        + len(candidate.evidence.liquidity_references)
    )
    return float(positive)


def _candidate_contradiction_count(candidate: TradeCandidate) -> float:
    return float(len(candidate.evidence.contradictions) + len(candidate.evidence.warnings))


def _collision_score(
    candidate: TradeCandidate,
    policy: CollisionResolutionPolicy,
) -> CollisionCandidateScore:
    quality_component = _candidate_quality_mean(candidate) * policy.quality_weight
    evidence_component = _candidate_evidence_strength(candidate) * policy.evidence_weight
    contradiction_penalty = (
        _candidate_contradiction_count(candidate) * policy.contradiction_penalty_weight
    )
    return CollisionCandidateScore(
        symbol=candidate.symbol,
        direction=candidate.direction,
        quality_component=quality_component,
        evidence_component=evidence_component,
        contradiction_penalty=contradiction_penalty,
        total=quality_component + evidence_component - contradiction_penalty,
    )


def audit_collision_resolution(
    left: TradeCandidate,
    right: TradeCandidate,
    *,
    policy: CollisionResolutionPolicy,
) -> CollisionResolutionAudit:
    """Compare colliding candidates without suppressing either candidate."""

    collision = audit_cmp_collision(left, right)
    left_score = _collision_score(left, policy)
    right_score = _collision_score(right, policy)
    advantage = left_score.total - right_score.total

    if not collision.unresolved_opposite_collision:
        resolution = CollisionResolution.NOT_APPLICABLE
    elif abs(advantage) < policy.minimum_advantage:
        resolution = CollisionResolution.NEUTRAL
    elif advantage > 0:
        resolution = CollisionResolution.LEFT
    else:
        resolution = CollisionResolution.RIGHT

    return CollisionResolutionAudit(
        collision=collision,
        left=left_score,
        right=right_score,
        advantage=advantage,
        resolution=resolution,
    )


class SequenceDisposition(StrEnum):
    """Diagnostic validity of two opposite opportunities in sequence."""

    VALID_SEQUENCE = "valid_sequence"
    UNRESOLVED_COLLISION = "unresolved_collision"
    DUPLICATE_THESIS = "duplicate_thesis"
    INVALID_ORDER = "invalid_order"
    NOT_APPLICABLE = "not_applicable"


class SequenceReason(StrEnum):
    """Machine-readable reasons for sequence validation."""

    DIFFERENT_SYMBOL = "different_symbol"
    SAME_DIRECTION = "same_direction"
    ENTRY_ZONES_OVERLAP = "entry_zones_overlap"
    CURRENT_NOT_EXECUTABLE = "current_not_executable"
    FOLLOW_UP_ALREADY_EXECUTABLE = "follow_up_already_executable"
    FOLLOW_UP_NOT_DIRECTIONALLY_SEPARATED = "follow_up_not_directionally_separated"
    SHARED_INVALIDATION = "shared_invalidation"
    INSUFFICIENT_INDEPENDENT_EVIDENCE = "insufficient_independent_evidence"


@dataclass(frozen=True, slots=True)
class OpportunitySequencePolicy:
    """Explicit rules for validating sequential opposite opportunities."""

    minimum_zone_gap: float = 0.0
    require_distinct_invalidation: bool = True
    require_independent_evidence: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(self.minimum_zone_gap):
            raise ValueError("minimum zone gap must be finite")
        if self.minimum_zone_gap < 0:
            raise ValueError("minimum zone gap cannot be negative")


@dataclass(frozen=True, slots=True)
class OpportunitySequenceAudit:
    """Read-only explanation of whether opposite setups can coexist."""

    current_symbol: str
    follow_up_symbol: str
    current_direction: TradeDirection
    follow_up_direction: TradeDirection
    disposition: SequenceDisposition
    reasons: tuple[SequenceReason, ...]
    zone_gap: float
    current_executable: bool
    follow_up_executable: bool
    independent_invalidation: bool
    independent_evidence: bool

    @property
    def can_coexist(self) -> bool:
        return self.disposition is SequenceDisposition.VALID_SEQUENCE


def _zone_contains_current(candidate: TradeCandidate) -> bool:
    return candidate.entry.lower <= candidate.entry.current_price <= candidate.entry.upper


def _zone_gap(left: TradeCandidate, right: TradeCandidate) -> float:
    if left.entry.upper < right.entry.lower:
        return right.entry.lower - left.entry.upper
    if right.entry.upper < left.entry.lower:
        return left.entry.lower - right.entry.upper
    return 0.0


def _evidence_signature(candidate: TradeCandidate) -> frozenset[str]:
    return frozenset(
        (
            *candidate.evidence.supporting,
            *candidate.evidence.feature_references,
            *candidate.evidence.structure_references,
            *candidate.evidence.liquidity_references,
        )
    )


def _has_independent_evidence(
    current: TradeCandidate,
    follow_up: TradeCandidate,
) -> bool:
    current_signature = _evidence_signature(current)
    follow_up_signature = _evidence_signature(follow_up)
    if current.strategy is not follow_up.strategy:
        return True
    if not current_signature or not follow_up_signature:
        return False
    return current_signature != follow_up_signature


def _is_directionally_separated_follow_up(
    current: TradeCandidate,
    follow_up: TradeCandidate,
) -> bool:
    if current.direction is TradeDirection.SHORT:
        return follow_up.entry.upper < current.entry.lower
    return follow_up.entry.lower > current.entry.upper


def audit_opportunity_sequence(
    current: TradeCandidate,
    follow_up: TradeCandidate,
    *,
    policy: OpportunitySequencePolicy,
) -> OpportunitySequenceAudit:
    """Validate opposite opportunities as an ordered, read-only sequence."""

    collision = audit_cmp_collision(current, follow_up)
    current_executable = _zone_contains_current(current)
    follow_up_executable = _zone_contains_current(follow_up)
    zone_gap = _zone_gap(current, follow_up)
    independent_invalidation = not math.isclose(
        current.invalidation.price,
        follow_up.invalidation.price,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    independent_evidence = _has_independent_evidence(current, follow_up)
    reasons: list[SequenceReason] = []

    if current.symbol != follow_up.symbol:
        reasons.append(SequenceReason.DIFFERENT_SYMBOL)
    if current.direction is follow_up.direction:
        reasons.append(SequenceReason.SAME_DIRECTION)

    applicable = not reasons
    if applicable and collision.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP:
        reasons.append(SequenceReason.ENTRY_ZONES_OVERLAP)
    if applicable and not current_executable:
        reasons.append(SequenceReason.CURRENT_NOT_EXECUTABLE)
    if applicable and follow_up_executable:
        reasons.append(SequenceReason.FOLLOW_UP_ALREADY_EXECUTABLE)
    if (
        applicable
        and collision.kind is CollisionKind.NONE
        and (
            zone_gap < policy.minimum_zone_gap
            or not _is_directionally_separated_follow_up(current, follow_up)
        )
    ):
        reasons.append(SequenceReason.FOLLOW_UP_NOT_DIRECTIONALLY_SEPARATED)
    if applicable and policy.require_distinct_invalidation and not independent_invalidation:
        reasons.append(SequenceReason.SHARED_INVALIDATION)
    if applicable and policy.require_independent_evidence and not independent_evidence:
        reasons.append(SequenceReason.INSUFFICIENT_INDEPENDENT_EVIDENCE)

    reason_set = set(reasons)
    if SequenceReason.DIFFERENT_SYMBOL in reason_set or SequenceReason.SAME_DIRECTION in reason_set:
        disposition = SequenceDisposition.NOT_APPLICABLE
    elif SequenceReason.ENTRY_ZONES_OVERLAP in reason_set:
        disposition = SequenceDisposition.UNRESOLVED_COLLISION
    elif (
        SequenceReason.SHARED_INVALIDATION in reason_set
        or SequenceReason.INSUFFICIENT_INDEPENDENT_EVIDENCE in reason_set
    ):
        disposition = SequenceDisposition.DUPLICATE_THESIS
    elif reasons:
        disposition = SequenceDisposition.INVALID_ORDER
    else:
        disposition = SequenceDisposition.VALID_SEQUENCE

    return OpportunitySequenceAudit(
        current_symbol=current.symbol,
        follow_up_symbol=follow_up.symbol,
        current_direction=current.direction,
        follow_up_direction=follow_up.direction,
        disposition=disposition,
        reasons=tuple(reasons),
        zone_gap=zone_gap,
        current_executable=current_executable,
        follow_up_executable=follow_up_executable,
        independent_invalidation=independent_invalidation,
        independent_evidence=independent_evidence,
    )


__all__ = [
    "CollisionCandidateScore",
    "CollisionKind",
    "CollisionResolution",
    "CollisionResolutionAudit",
    "CollisionResolutionPolicy",
    "EntryZoneOverlap",
    "OpportunityCollisionAudit",
    "OpportunitySequenceAudit",
    "OpportunitySequencePolicy",
    "SequenceDisposition",
    "SequenceReason",
    "audit_cmp_collision",
    "audit_collision_resolution",
    "audit_opportunity_sequence",
]
