"""Read-only market-evidence availability and freshness diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EvidenceRequirement(StrEnum):
    """How strongly one evidence input is required by a consumer."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class EvidenceState(StrEnum):
    """Observed usability state for one market-evidence input."""

    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"
    UNSYNCHRONIZED = "unsynchronized"


class DataQualityDisposition(StrEnum):
    """Overall diagnostic quality of the supplied evidence set."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    INSUFFICIENT = "insufficient"


class MarketEvidenceKind(StrEnum):
    """High-value evidence families planned for Batch 9."""

    AGGREGATE_TRADE_IMBALANCE = "aggregate_trade_imbalance"
    PRICE_OPEN_INTEREST_RELATIONSHIP = "price_open_interest_relationship"
    BREAKOUT_ACCEPTANCE_DURATION = "breakout_acceptance_duration"
    PULLBACK_VOLUME_DECAY = "pullback_volume_decay"
    SPREAD_DETERIORATION = "spread_deterioration"
    DEPTH_IMBALANCE = "depth_imbalance"
    LIQUIDATION_IMPULSE = "liquidation_impulse"


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessPolicy:
    """Explicit freshness and synchronization limits for one evidence input."""

    maximum_age_seconds: int
    maximum_clock_skew_seconds: int

    def __post_init__(self) -> None:
        if self.maximum_age_seconds < 0:
            raise ValueError("maximum evidence age cannot be negative")
        if self.maximum_clock_skew_seconds < 0:
            raise ValueError("maximum clock skew cannot be negative")


@dataclass(frozen=True, slots=True)
class MarketEvidenceObservation:
    """Read-only observation of one derived or externally supplied input."""

    kind: MarketEvidenceKind
    requirement: EvidenceRequirement
    observed_at: datetime | None
    source_timestamp: datetime | None
    value_available: bool
    synchronization_valid: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("observed time", self.observed_at),
            ("source timestamp", self.source_timestamp),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MarketEvidenceAudit:
    """Diagnostic result for one market-evidence observation."""

    kind: MarketEvidenceKind
    requirement: EvidenceRequirement
    state: EvidenceState
    age_seconds: float | None
    clock_skew_seconds: float | None

    @property
    def usable(self) -> bool:
        return self.state is EvidenceState.AVAILABLE

    @property
    def blocks_required_decision(self) -> bool:
        return self.requirement is EvidenceRequirement.REQUIRED and not self.usable


@dataclass(frozen=True, slots=True)
class MarketEvidenceSetAudit:
    """Aggregate evidence-quality result without changing live decisions."""

    disposition: DataQualityDisposition
    evidence: tuple[MarketEvidenceAudit, ...]
    required_failures: tuple[MarketEvidenceKind, ...]
    optional_failures: tuple[MarketEvidenceKind, ...]

    @property
    def complete(self) -> bool:
        return self.disposition is DataQualityDisposition.COMPLETE


def audit_market_evidence(
    observation: MarketEvidenceObservation,
    *,
    evaluated_at: datetime,
    policy: EvidenceFreshnessPolicy,
) -> MarketEvidenceAudit:
    """Classify one evidence input without treating absence as negative evidence."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluation time must be timezone-aware")

    if (
        not observation.value_available
        or observation.observed_at is None
        or observation.source_timestamp is None
    ):
        return MarketEvidenceAudit(
            kind=observation.kind,
            requirement=observation.requirement,
            state=EvidenceState.MISSING,
            age_seconds=None,
            clock_skew_seconds=None,
        )

    age_seconds = (evaluated_at - observation.observed_at).total_seconds()
    clock_skew_seconds = abs(
        (observation.observed_at - observation.source_timestamp).total_seconds()
    )
    if not math.isfinite(age_seconds) or not math.isfinite(clock_skew_seconds):
        raise ValueError("evidence timing values must be finite")
    if age_seconds < 0:
        raise ValueError("evidence observation cannot be from the future")

    if (
        not observation.synchronization_valid
        or clock_skew_seconds > policy.maximum_clock_skew_seconds
    ):
        state = EvidenceState.UNSYNCHRONIZED
    elif age_seconds > policy.maximum_age_seconds:
        state = EvidenceState.STALE
    else:
        state = EvidenceState.AVAILABLE

    return MarketEvidenceAudit(
        kind=observation.kind,
        requirement=observation.requirement,
        state=state,
        age_seconds=age_seconds,
        clock_skew_seconds=clock_skew_seconds,
    )


def audit_market_evidence_set(
    observations: tuple[MarketEvidenceObservation, ...],
    *,
    evaluated_at: datetime,
    policies: dict[MarketEvidenceKind, EvidenceFreshnessPolicy],
) -> MarketEvidenceSetAudit:
    """Aggregate evidence diagnostics with required/optional degradation semantics."""

    kinds = tuple(observation.kind for observation in observations)
    if len(set(kinds)) != len(kinds):
        raise ValueError("market evidence kinds must be unique")

    audits: list[MarketEvidenceAudit] = []
    for observation in observations:
        try:
            policy = policies[observation.kind]
        except KeyError as error:
            raise ValueError(f"missing freshness policy for {observation.kind.value}") from error
        audits.append(
            audit_market_evidence(
                observation,
                evaluated_at=evaluated_at,
                policy=policy,
            )
        )

    required_failures = tuple(audit.kind for audit in audits if audit.blocks_required_decision)
    optional_failures = tuple(
        audit.kind
        for audit in audits
        if audit.requirement is EvidenceRequirement.OPTIONAL and not audit.usable
    )

    if required_failures:
        disposition = DataQualityDisposition.INSUFFICIENT
    elif optional_failures:
        disposition = DataQualityDisposition.DEGRADED
    else:
        disposition = DataQualityDisposition.COMPLETE

    return MarketEvidenceSetAudit(
        disposition=disposition,
        evidence=tuple(audits),
        required_failures=required_failures,
        optional_failures=optional_failures,
    )


__all__ = [
    "DataQualityDisposition",
    "EvidenceFreshnessPolicy",
    "EvidenceRequirement",
    "EvidenceState",
    "MarketEvidenceAudit",
    "MarketEvidenceKind",
    "MarketEvidenceObservation",
    "MarketEvidenceSetAudit",
    "audit_market_evidence",
    "audit_market_evidence_set",
]
