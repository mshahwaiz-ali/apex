"""Deterministic execution-quality component model.

This module scores actual execution conditions independently from setup quality.
Hard caps and candidate integration are added in later Batch 9 patches.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType

_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "location": 0.20,
        "trigger_completion": 0.20,
        "freshness": 0.15,
        "spread_slippage": 0.10,
        "stop_feasibility": 0.15,
        "chase_safety": 0.10,
        "data_quality": 0.10,
    }
)


def _unit_interval(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between zero and one")


@dataclass(frozen=True, slots=True)
class ExecutionQualityInputs:
    """Normalized inputs describing whether a setup is executable now."""

    location: float
    trigger_completion: float
    freshness: float
    spread_slippage: float
    stop_feasibility: float
    chase_safety: float
    data_quality: float

    def __post_init__(self) -> None:
        for item in fields(self):
            _unit_interval(item.name.replace("_", " "), getattr(self, item.name))


@dataclass(frozen=True, slots=True)
class ExecutionQualityBreakdown:
    """Auditable component contributions to the uncapped score."""

    location: float
    trigger_completion: float
    freshness: float
    spread_slippage: float
    stop_feasibility: float
    chase_safety: float
    data_quality: float

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(
                    f"{item.name.replace('_', ' ')} contribution must be non-negative and finite"
                )

    @property
    def total(self) -> float:
        """Return the sum of weighted component contributions."""

        return (
            self.location
            + self.trigger_completion
            + self.freshness
            + self.spread_slippage
            + self.stop_feasibility
            + self.chase_safety
            + self.data_quality
        )

    def as_mapping(self) -> Mapping[str, float]:
        """Expose immutable component values for JSON and CLI serializers."""

        return MappingProxyType({item.name: getattr(self, item.name) for item in fields(self)})


@dataclass(frozen=True, slots=True)
class ExecutionQualityResult:
    """Uncapped execution-quality result with full explanation."""

    score: float
    breakdown: ExecutionQualityBreakdown
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _unit_interval("execution quality score", self.score)
        if not math.isclose(self.score, self.breakdown.total, abs_tol=1e-12):
            raise ValueError("execution quality score must equal component total")
        if not self.reasons:
            raise ValueError("execution quality requires explanatory reasons")


def calculate_execution_quality(
    inputs: ExecutionQualityInputs,
) -> ExecutionQualityResult:
    """Calculate an uncapped 0-1 execution-quality score."""

    contributions = {name: getattr(inputs, name) * weight for name, weight in _WEIGHTS.items()}
    breakdown = ExecutionQualityBreakdown(**contributions)
    reasons = tuple(
        f"{name.replace('_', ' ')} contributes {contribution:.3f} "
        f"from normalized input {getattr(inputs, name):.3f}"
        for name, contribution in contributions.items()
    )
    return ExecutionQualityResult(
        score=breakdown.total,
        breakdown=breakdown,
        reasons=reasons,
    )


@dataclass(frozen=True, slots=True)
class ExecutionQualityConstraints:
    """Execution facts that may cap an otherwise strong component score."""

    provisional_evidence: bool = False
    trigger_complete: bool = True
    data_stale: bool = False
    data_degraded: bool = False
    inside_entry_zone: bool = True
    chase_limit_violated: bool = False
    stop_feasible: bool = True
    spread_slippage_available: bool = True


@dataclass(frozen=True, slots=True)
class CappedExecutionQualityResult:
    """Raw score plus deterministic execution caps and final score."""

    uncapped_score: float
    applied_cap: float
    final_score: float
    cap_reasons: tuple[str, ...]
    breakdown: ExecutionQualityBreakdown
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _unit_interval("uncapped execution quality score", self.uncapped_score)
        _unit_interval("execution quality cap", self.applied_cap)
        _unit_interval("final execution quality score", self.final_score)
        if not math.isclose(
            self.final_score,
            min(self.uncapped_score, self.applied_cap),
            abs_tol=1e-12,
        ):
            raise ValueError("final execution score must equal uncapped score limited by cap")
        if not math.isclose(
            self.uncapped_score,
            self.breakdown.total,
            abs_tol=1e-12,
        ):
            raise ValueError("uncapped score must equal component total")
        if self.applied_cap < 1.0 and not self.cap_reasons:
            raise ValueError("a restrictive execution cap requires a reason")
        if not self.reasons:
            raise ValueError("capped execution quality requires explanatory reasons")


@dataclass(frozen=True, slots=True)
class ExecutionQualityCapPolicy:
    """Runtime hard-cap policy resolved from validated configuration."""

    provisional_evidence: float = 0.65
    trigger_incomplete: float = 0.55
    data_stale: float = 0.25
    data_degraded: float = 0.50
    outside_entry_zone: float = 0.60
    chase_limit_violated: float = 0.20
    stop_infeasible: float = 0.00
    spread_slippage_unavailable: float = 0.75

    def __post_init__(self) -> None:
        for item in fields(self):
            _unit_interval(item.name.replace("_", " "), getattr(self, item.name))

    def rules(self) -> tuple[tuple[str, float, str], ...]:
        return (
            (
                "provisional_evidence",
                self.provisional_evidence,
                "active-candle evidence is provisional",
            ),
            (
                "trigger_incomplete",
                self.trigger_incomplete,
                "entry trigger or confirmation is incomplete",
            ),
            ("data_stale", self.data_stale, "market data is stale"),
            ("data_degraded", self.data_degraded, "market data quality is degraded"),
            (
                "outside_entry_zone",
                self.outside_entry_zone,
                "current price is outside the canonical entry zone",
            ),
            (
                "chase_limit_violated",
                self.chase_limit_violated,
                "current price violated the maximum chase boundary",
            ),
            ("stop_infeasible", self.stop_infeasible, "stop geometry is infeasible"),
            (
                "spread_slippage_unavailable",
                self.spread_slippage_unavailable,
                "spread and slippage evidence is unavailable",
            ),
        )


DEFAULT_EXECUTION_QUALITY_CAP_POLICY = ExecutionQualityCapPolicy()


def apply_execution_quality_caps(
    result: ExecutionQualityResult,
    constraints: ExecutionQualityConstraints,
    *,
    policy: ExecutionQualityCapPolicy = DEFAULT_EXECUTION_QUALITY_CAP_POLICY,
) -> CappedExecutionQualityResult:
    """Apply the strictest relevant execution cap without hiding raw quality."""

    active: list[tuple[float, str]] = []
    flags = {
        "provisional_evidence": constraints.provisional_evidence,
        "trigger_incomplete": not constraints.trigger_complete,
        "data_stale": constraints.data_stale,
        "data_degraded": constraints.data_degraded,
        "outside_entry_zone": not constraints.inside_entry_zone,
        "chase_limit_violated": constraints.chase_limit_violated,
        "stop_infeasible": not constraints.stop_feasible,
        "spread_slippage_unavailable": not constraints.spread_slippage_available,
    }
    for key, cap, reason in policy.rules():
        if flags[key]:
            active.append((cap, reason))

    applied_cap = min((cap for cap, _ in active), default=1.0)
    cap_reasons = tuple(reason for cap, reason in active if cap == applied_cap)
    final_score = min(result.score, applied_cap)
    reasons = (
        *result.reasons,
        (
            f"execution quality capped at {applied_cap:.2f}"
            if applied_cap < 1.0
            else "no execution-quality cap applied"
        ),
        *cap_reasons,
    )
    return CappedExecutionQualityResult(
        uncapped_score=result.score,
        applied_cap=applied_cap,
        final_score=final_score,
        cap_reasons=cap_reasons,
        breakdown=result.breakdown,
        reasons=reasons,
    )


def execution_quality_weights() -> Mapping[str, float]:
    """Return immutable canonical component weights."""

    return _WEIGHTS


__all__ = [
    "DEFAULT_EXECUTION_QUALITY_CAP_POLICY",
    "CappedExecutionQualityResult",
    "ExecutionQualityBreakdown",
    "ExecutionQualityCapPolicy",
    "ExecutionQualityConstraints",
    "ExecutionQualityInputs",
    "ExecutionQualityResult",
    "apply_execution_quality_caps",
    "calculate_execution_quality",
    "execution_quality_weights",
]
