"""Deterministic portfolio-retention and suppression audit contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.opportunity_portfolio import (
    OpportunityLane,
    SequenceRole,
    classify_setup_opportunity_lane,
    classify_setup_sequence_role,
    setup_is_portfolio_eligible,
)


class PortfolioSuppressionReason(StrEnum):
    """Machine-readable reasons why a setup did not retain a portfolio slot."""

    INELIGIBLE_SETUP = "ineligible_setup"
    DUPLICATE_CANDIDATE_ID = "duplicate_candidate_id"
    DUPLICATE_GEOMETRY = "duplicate_geometry"
    LOWER_PRIORITY_SAME_LANE = "lower_priority_same_lane"
    OPPOSING_DIRECTION_COLLISION = "opposing_direction_collision"


@dataclass(frozen=True, slots=True)
class PortfolioRetentionRecord:
    candidate_id: str
    lane: OpportunityLane
    sequence_role: SequenceRole
    retained: bool
    suppression_reason: PortfolioSuppressionReason | None
    retained_candidate_id: str | None
    geometry_fingerprint: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class PortfolioRetentionAudit:
    records: tuple[PortfolioRetentionRecord, ...]

    @property
    def retained_candidate_ids(self) -> tuple[str, ...]:
        return tuple(record.candidate_id for record in self.records if record.retained)

    @property
    def suppressed_candidate_ids(self) -> tuple[str, ...]:
        return tuple(record.candidate_id for record in self.records if not record.retained)


def setup_geometry_fingerprint(
    setup: DiscoverySetup,
    *,
    tick_size: float | None = None,
) -> tuple[object, ...]:
    """Return true trade-geometry identity without using strategy or candidate ID."""

    if tick_size is not None and tick_size <= 0.0:
        raise ValueError("tick size must be positive when provided")

    def normalize(value: float) -> float | int:
        if tick_size is None:
            return value
        return round(value / tick_size)

    return (
        setup.direction.value,
        normalize(setup.entry.lower),
        normalize(setup.entry.preferred),
        normalize(setup.entry.upper),
        normalize(setup.entry.maximum_chase_price),
        normalize(setup.stop_loss.price),
        tuple(
            (
                target.target_type.value,
                normalize(target.price),
                target.target_role.value,
            )
            for target in setup.take_profits
        ),
    )


def _entry_zones_overlap(
    left: DiscoverySetup,
    right: DiscoverySetup,
) -> bool:
    return max(left.entry.lower, right.entry.lower) <= min(
        left.entry.upper,
        right.entry.upper,
    )


def _is_direct_opposing_collision(
    candidate: DiscoverySetup,
    retained: DiscoverySetup,
    *,
    candidate_lane: OpportunityLane,
    retained_lane: OpportunityLane,
    candidate_role: SequenceRole,
    retained_role: SequenceRole,
) -> bool:
    """Return whether two setups are mutually exclusive current instructions."""

    return (
        candidate.direction is not retained.direction
        and candidate_lane is retained_lane
        and candidate_role is SequenceRole.CURRENT
        and retained_role is SequenceRole.CURRENT
        and candidate.execution_allowed_now
        and retained.execution_allowed_now
        and _entry_zones_overlap(candidate, retained)
    )


def build_portfolio_retention_audit(
    setups: Iterable[DiscoverySetup],
    *,
    tick_size: float | None = None,
) -> PortfolioRetentionAudit:
    """Retain one deterministic best candidate per lane/direction and trace suppression."""

    materialized = tuple(setups)
    seen_ids: set[str] = set()
    retained_geometry: dict[tuple[object, ...], str] = {}
    retained_lane: dict[tuple[OpportunityLane, object], str] = {}
    retained_setups: dict[str, DiscoverySetup] = {}
    records: list[PortfolioRetentionRecord] = []

    ordered = sorted(
        materialized,
        key=lambda setup: (
            -setup.confidence_score,
            setup.candidate_id,
        ),
    )
    for setup in ordered:
        role = classify_setup_sequence_role(setup)
        lane = classify_setup_opportunity_lane(setup, sequence_role=role)
        fingerprint = setup_geometry_fingerprint(setup, tick_size=tick_size)

        reason: PortfolioSuppressionReason | None = None
        retained_candidate_id: str | None = None
        if not setup_is_portfolio_eligible(setup):
            reason = PortfolioSuppressionReason.INELIGIBLE_SETUP
        elif setup.candidate_id in seen_ids:
            reason = PortfolioSuppressionReason.DUPLICATE_CANDIDATE_ID
            retained_candidate_id = setup.candidate_id
        elif fingerprint in retained_geometry:
            reason = PortfolioSuppressionReason.DUPLICATE_GEOMETRY
            retained_candidate_id = retained_geometry[fingerprint]
        else:
            for retained_id, retained_setup in retained_setups.items():
                retained_role = classify_setup_sequence_role(retained_setup)
                retained_opportunity_lane = classify_setup_opportunity_lane(
                    retained_setup,
                    sequence_role=retained_role,
                )
                if _is_direct_opposing_collision(
                    setup,
                    retained_setup,
                    candidate_lane=lane,
                    retained_lane=retained_opportunity_lane,
                    candidate_role=role,
                    retained_role=retained_role,
                ):
                    reason = PortfolioSuppressionReason.OPPOSING_DIRECTION_COLLISION
                    retained_candidate_id = retained_id
                    break

            lane_key = (lane, setup.direction)
            if reason is None and lane_key in retained_lane:
                reason = PortfolioSuppressionReason.LOWER_PRIORITY_SAME_LANE
                retained_candidate_id = retained_lane[lane_key]

        retained = reason is None
        if retained:
            seen_ids.add(setup.candidate_id)
            retained_geometry[fingerprint] = setup.candidate_id
            retained_lane[(lane, setup.direction)] = setup.candidate_id
            retained_setups[setup.candidate_id] = setup

        records.append(
            PortfolioRetentionRecord(
                candidate_id=setup.candidate_id,
                lane=lane,
                sequence_role=role,
                retained=retained,
                suppression_reason=reason,
                retained_candidate_id=retained_candidate_id,
                geometry_fingerprint=fingerprint,
            )
        )

    return PortfolioRetentionAudit(records=tuple(records))


def portfolio_retention_audit_payload(
    audit: PortfolioRetentionAudit,
) -> dict[str, object]:
    """Serialize retention decisions without exposing Python-only enum objects."""

    retained = tuple(record for record in audit.records if record.retained)
    suppressed = tuple(record for record in audit.records if not record.retained)
    return {
        "candidate_count": len(audit.records),
        "retained_count": len(retained),
        "suppressed_count": len(suppressed),
        "duplicate_suppressed_count": sum(
            record.suppression_reason
            in {
                PortfolioSuppressionReason.DUPLICATE_CANDIDATE_ID,
                PortfolioSuppressionReason.DUPLICATE_GEOMETRY,
            }
            for record in suppressed
        ),
        "collision_suppressed_count": sum(
            record.suppression_reason is PortfolioSuppressionReason.OPPOSING_DIRECTION_COLLISION
            for record in suppressed
        ),
        "retained_candidate_ids": list(audit.retained_candidate_ids),
        "suppressed_candidate_ids": list(audit.suppressed_candidate_ids),
        "records": [
            {
                "candidate_id": record.candidate_id,
                "lane": record.lane.value,
                "sequence_role": record.sequence_role.value,
                "retained": record.retained,
                "suppression_reason": (
                    None if record.suppression_reason is None else record.suppression_reason.value
                ),
                "retained_candidate_id": record.retained_candidate_id,
                "geometry_fingerprint": list(record.geometry_fingerprint),
            }
            for record in audit.records
        ],
    }


__all__ = [
    "PortfolioRetentionAudit",
    "PortfolioRetentionRecord",
    "PortfolioSuppressionReason",
    "build_portfolio_retention_audit",
    "portfolio_retention_audit_payload",
    "setup_geometry_fingerprint",
]
