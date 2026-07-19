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


@dataclass(frozen=True, slots=True)
class ExecutionStopGeometry:
    """Executable stop derived beyond structural invalidation."""

    direction: TradeDirection
    preferred_entry: float
    structural_invalidation: float
    execution_buffer: float
    executable_stop: float
    structural_risk_distance: float
    executable_risk_distance: float

    def __post_init__(self) -> None:
        values = (
            self.preferred_entry,
            self.structural_invalidation,
            self.execution_buffer,
            self.executable_stop,
            self.structural_risk_distance,
            self.executable_risk_distance,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("execution-stop geometry values must be finite")
        if self.preferred_entry <= 0:
            raise ValueError("preferred entry must be positive")
        if self.structural_invalidation <= 0:
            raise ValueError("structural invalidation must be positive")
        if self.execution_buffer < 0:
            raise ValueError("execution buffer cannot be negative")
        if self.executable_stop <= 0:
            raise ValueError("executable stop must be positive")

        if self.direction is TradeDirection.LONG:
            if self.structural_invalidation >= self.preferred_entry:
                raise ValueError("long structural invalidation must be below preferred entry")
            if self.executable_stop > self.structural_invalidation:
                raise ValueError("long executable stop cannot be above structural invalidation")
        else:
            if self.structural_invalidation <= self.preferred_entry:
                raise ValueError("short structural invalidation must be above preferred entry")
            if self.executable_stop < self.structural_invalidation:
                raise ValueError("short executable stop cannot be below structural invalidation")

        if self.structural_risk_distance <= 0:
            raise ValueError("structural risk distance must be positive")
        if self.executable_risk_distance <= 0:
            raise ValueError("executable risk distance must be positive")


def derive_execution_stop_geometry(
    *,
    direction: TradeDirection,
    preferred_entry: float,
    structural_invalidation: float,
    execution_buffer: float,
) -> ExecutionStopGeometry:
    """Derive an executable stop beyond structural invalidation."""

    values = (
        preferred_entry,
        structural_invalidation,
        execution_buffer,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("execution-stop inputs must be finite")
    if execution_buffer < 0:
        raise ValueError("execution buffer cannot be negative")

    if direction is TradeDirection.LONG:
        executable_stop = structural_invalidation - execution_buffer
        structural_risk = preferred_entry - structural_invalidation
        executable_risk = preferred_entry - executable_stop
    else:
        executable_stop = structural_invalidation + execution_buffer
        structural_risk = structural_invalidation - preferred_entry
        executable_risk = executable_stop - preferred_entry

    return ExecutionStopGeometry(
        direction=direction,
        preferred_entry=preferred_entry,
        structural_invalidation=structural_invalidation,
        execution_buffer=execution_buffer,
        executable_stop=executable_stop,
        structural_risk_distance=structural_risk,
        executable_risk_distance=executable_risk,
    )


@dataclass(frozen=True, slots=True)
class ExecutionBufferPolicy:
    """Deterministic policy inputs for executable-stop buffering."""

    atr_multiplier: float
    spread_multiplier: float
    minimum_buffer: float = 0.0
    maximum_buffer: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.atr_multiplier,
            self.spread_multiplier,
            self.minimum_buffer,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("execution-buffer policy values must be finite")
        if self.atr_multiplier < 0:
            raise ValueError("ATR multiplier cannot be negative")
        if self.spread_multiplier < 0:
            raise ValueError("spread multiplier cannot be negative")
        if self.minimum_buffer < 0:
            raise ValueError("minimum buffer cannot be negative")
        if self.maximum_buffer is not None:
            if not math.isfinite(self.maximum_buffer):
                raise ValueError("maximum buffer must be finite")
            if self.maximum_buffer < 0:
                raise ValueError("maximum buffer cannot be negative")
            if self.maximum_buffer < self.minimum_buffer:
                raise ValueError("maximum buffer cannot be below minimum buffer")


@dataclass(frozen=True, slots=True)
class ExecutionBufferDecision:
    """Read-only execution-buffer decision and component values."""

    atr_component: float
    spread_component: float
    unclamped_buffer: float
    execution_buffer: float
    floor_applied: bool
    cap_applied: bool


def derive_execution_buffer(
    *,
    atr: float,
    spread: float,
    policy: ExecutionBufferPolicy,
) -> ExecutionBufferDecision:
    """Derive a deterministic buffer from ATR and spread observations."""

    if not math.isfinite(atr):
        raise ValueError("ATR must be finite")
    if not math.isfinite(spread):
        raise ValueError("spread must be finite")
    if atr < 0:
        raise ValueError("ATR cannot be negative")
    if spread < 0:
        raise ValueError("spread cannot be negative")

    atr_component = atr * policy.atr_multiplier
    spread_component = spread * policy.spread_multiplier
    unclamped = max(atr_component, spread_component)

    execution_buffer = max(unclamped, policy.minimum_buffer)
    floor_applied = execution_buffer > unclamped
    cap_applied = False

    if policy.maximum_buffer is not None and execution_buffer > policy.maximum_buffer:
        execution_buffer = policy.maximum_buffer
        cap_applied = True

    return ExecutionBufferDecision(
        atr_component=atr_component,
        spread_component=spread_component,
        unclamped_buffer=unclamped,
        execution_buffer=execution_buffer,
        floor_applied=floor_applied,
        cap_applied=cap_applied,
    )


@dataclass(frozen=True, slots=True)
class ExecutableTargetAudit:
    """Target reward geometry measured against an executable stop."""

    label: str
    kind: TargetType
    price: float
    reward_distance: float
    executable_reward_to_risk: float


@dataclass(frozen=True, slots=True)
class ExecutableRiskTargetAudit:
    """Read-only target audit using executable rather than structural risk."""

    direction: TradeDirection
    preferred_entry: float
    executable_stop: float
    executable_risk_distance: float
    targets: tuple[ExecutableTargetAudit, ...]

    @property
    def minimum_reward_to_risk(self) -> float:
        return min(target.executable_reward_to_risk for target in self.targets)

    @property
    def maximum_reward_to_risk(self) -> float:
        return max(target.executable_reward_to_risk for target in self.targets)


def audit_targets_against_executable_stop(
    *,
    candidate: TradeCandidate,
    stop_geometry: ExecutionStopGeometry,
) -> ExecutableRiskTargetAudit:
    """Measure existing targets against independently derived executable risk."""

    if candidate.direction is not stop_geometry.direction:
        raise ValueError("candidate and stop geometry directions must match")
    if not math.isclose(
        candidate.entry.preferred,
        stop_geometry.preferred_entry,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("candidate and stop geometry preferred entries must match")
    if not math.isclose(
        candidate.invalidation.price,
        stop_geometry.structural_invalidation,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("candidate invalidation and stop geometry structure must match")

    if candidate.direction is TradeDirection.LONG:
        rewards = tuple(
            level.price - candidate.entry.preferred for level in candidate.targets.levels
        )
    else:
        rewards = tuple(
            candidate.entry.preferred - level.price for level in candidate.targets.levels
        )

    if any(reward <= 0 for reward in rewards):
        raise ValueError("all target rewards must be positive")
    if stop_geometry.executable_risk_distance <= 0:
        raise ValueError("executable risk distance must be positive")

    targets = tuple(
        ExecutableTargetAudit(
            label=level.label,
            kind=level.kind,
            price=level.price,
            reward_distance=reward,
            executable_reward_to_risk=(reward / stop_geometry.executable_risk_distance),
        )
        for level, reward in zip(candidate.targets.levels, rewards, strict=True)
    )

    return ExecutableRiskTargetAudit(
        direction=candidate.direction,
        preferred_entry=candidate.entry.preferred,
        executable_stop=stop_geometry.executable_stop,
        executable_risk_distance=stop_geometry.executable_risk_distance,
        targets=targets,
    )


class TargetQualityTier(StrEnum):
    """Diagnostic quality tiers for executable-risk target geometry."""

    BELOW_MINIMUM = "below_minimum"
    ACCEPTABLE = "acceptable"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class TargetQualityPolicy:
    """Thresholds used only to classify existing targets."""

    minimum_reward_to_risk: float
    strong_reward_to_risk: float

    def __post_init__(self) -> None:
        values = (
            self.minimum_reward_to_risk,
            self.strong_reward_to_risk,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("target-quality thresholds must be finite")
        if self.minimum_reward_to_risk <= 0:
            raise ValueError("minimum reward-to-risk must be positive")
        if self.strong_reward_to_risk < self.minimum_reward_to_risk:
            raise ValueError("strong reward-to-risk cannot be below minimum reward-to-risk")


@dataclass(frozen=True, slots=True)
class TargetQualityAssessment:
    """Read-only target classification preserving original target identity."""

    label: str
    kind: TargetType
    price: float
    executable_reward_to_risk: float
    tier: TargetQualityTier
    is_structural: bool
    is_liquidity_based: bool


@dataclass(frozen=True, slots=True)
class TargetQualityAudit:
    """Diagnostic classification for all existing candidate targets."""

    assessments: tuple[TargetQualityAssessment, ...]

    @property
    def has_acceptable_target(self) -> bool:
        return any(item.tier is not TargetQualityTier.BELOW_MINIMUM for item in self.assessments)

    @property
    def has_strong_target(self) -> bool:
        return any(item.tier is TargetQualityTier.STRONG for item in self.assessments)


def classify_target_quality(
    *,
    target_audit: ExecutableRiskTargetAudit,
    policy: TargetQualityPolicy,
) -> TargetQualityAudit:
    """Classify existing targets without filtering, sorting, or mutation."""

    assessments = tuple(
        TargetQualityAssessment(
            label=target.label,
            kind=target.kind,
            price=target.price,
            executable_reward_to_risk=target.executable_reward_to_risk,
            tier=(
                TargetQualityTier.STRONG
                if target.executable_reward_to_risk >= policy.strong_reward_to_risk
                else (
                    TargetQualityTier.ACCEPTABLE
                    if target.executable_reward_to_risk >= policy.minimum_reward_to_risk
                    else TargetQualityTier.BELOW_MINIMUM
                )
            ),
            is_structural=target.kind is TargetType.STRUCTURAL,
            is_liquidity_based=target.kind is TargetType.LIQUIDITY,
        )
        for target in target_audit.targets
    )

    return TargetQualityAudit(assessments=assessments)


__all__ = [
    "CandidateGeometryAudit",
    "ExecutableRiskTargetAudit",
    "ExecutableTargetAudit",
    "ExecutionBufferDecision",
    "ExecutionBufferPolicy",
    "ExecutionStopGeometry",
    "GeometryIssueCode",
    "TargetGeometryAudit",
    "TargetQualityAssessment",
    "TargetQualityAudit",
    "TargetQualityPolicy",
    "TargetQualityTier",
    "audit_candidate_geometry",
    "audit_targets_against_executable_stop",
    "classify_target_quality",
    "derive_execution_buffer",
    "derive_execution_stop_geometry",
]
