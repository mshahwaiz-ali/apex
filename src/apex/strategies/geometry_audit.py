"""Read-only diagnostics for existing strategy candidate geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from apex.strategies.contracts import (
    TargetType,
    TradeCandidate,
    TradeDirection,
)


class GeometryIssueCode(StrEnum):
    """Machine-readable geometry diagnostic codes."""

    NON_POSITIVE_RISK = "non_positive_risk"
    NON_POSITIVE_REWARD = "non_positive_reward"
    TARGET_ORDER_INVALID = "target_order_invalid"
    NON_FINITE_VALUE = "non_finite_value"


@dataclass(frozen=True, slots=True)
class TargetGeometryAudit:
    """Read-only target geometry relative to the preferred entry."""

    label: str
    kind: TargetType
    price: float
    reward_distance: float
    reward_to_risk: float | None


@dataclass(frozen=True, slots=True)
class CandidateGeometryAudit:
    """Diagnostic projection that never changes candidate geometry."""

    symbol: str
    direction: TradeDirection
    preferred_entry: float
    entry_zone_low: float
    entry_zone_high: float
    structural_invalidation: float
    risk_distance: float
    targets: tuple[TargetGeometryAudit, ...]
    issues: tuple[GeometryIssueCode, ...]

    @property
    def is_consistent(self) -> bool:
        return not self.issues


def audit_candidate_geometry(candidate: TradeCandidate) -> CandidateGeometryAudit:
    """Project existing candidate geometry into deterministic diagnostics."""

    entry = candidate.entry.preferred
    invalidation = candidate.invalidation.price
    if candidate.direction is TradeDirection.LONG:
        risk_distance = entry - invalidation
        rewards = tuple(level.price - entry for level in candidate.targets.levels)
    else:
        risk_distance = invalidation - entry
        rewards = tuple(entry - level.price for level in candidate.targets.levels)

    issues: list[GeometryIssueCode] = []
    numeric_values = (
        entry,
        candidate.entry.lower,
        candidate.entry.upper,
        invalidation,
        risk_distance,
        *(level.price for level in candidate.targets.levels),
        *rewards,
    )
    if not all(math.isfinite(value) for value in numeric_values):
        issues.append(GeometryIssueCode.NON_FINITE_VALUE)
    if risk_distance <= 0:
        issues.append(GeometryIssueCode.NON_POSITIVE_RISK)
    if any(reward <= 0 for reward in rewards):
        issues.append(GeometryIssueCode.NON_POSITIVE_REWARD)

    prices = tuple(level.price for level in candidate.targets.levels)
    correctly_ordered = (
        all(left < right for left, right in pairwise(prices))
        if candidate.direction is TradeDirection.LONG
        else all(left > right for left, right in pairwise(prices))
    )
    if not correctly_ordered:
        issues.append(GeometryIssueCode.TARGET_ORDER_INVALID)

    target_audits = tuple(
        TargetGeometryAudit(
            label=level.label,
            kind=level.kind,
            price=level.price,
            reward_distance=reward,
            reward_to_risk=(
                reward / risk_distance
                if risk_distance > 0 and math.isfinite(reward / risk_distance)
                else None
            ),
        )
        for level, reward in zip(candidate.targets.levels, rewards, strict=True)
    )

    return CandidateGeometryAudit(
        symbol=candidate.symbol,
        direction=candidate.direction,
        preferred_entry=entry,
        entry_zone_low=candidate.entry.lower,
        entry_zone_high=candidate.entry.upper,
        structural_invalidation=invalidation,
        risk_distance=risk_distance,
        targets=target_audits,
        issues=tuple(dict.fromkeys(issues)),
    )


__all__ = [
    "CandidateGeometryAudit",
    "GeometryIssueCode",
    "TargetGeometryAudit",
    "audit_candidate_geometry",
]
