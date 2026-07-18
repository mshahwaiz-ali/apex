"""Canonical evidence for target obstacles and execution costs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_contracts import TargetRole


def _non_negative(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


class TargetObstacleRelation(StrEnum):
    """Position of a target relative to the nearest opposing structure."""

    BEFORE = "before"
    AT = "at"
    BEYOND = "beyond"


@dataclass(frozen=True, slots=True)
class ExecutionCostEstimate:
    """Round-trip cost estimate used for net reward geometry."""

    entry_fee_percentage: float
    exit_fee_percentage: float
    spread_percentage: float
    entry_slippage_percentage: float
    exit_slippage_percentage: float
    funding_percentage: float = 0.0
    source: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("entry fee percentage", self.entry_fee_percentage),
            ("exit fee percentage", self.exit_fee_percentage),
            ("spread percentage", self.spread_percentage),
            ("entry slippage percentage", self.entry_slippage_percentage),
            ("exit slippage percentage", self.exit_slippage_percentage),
            ("funding percentage", self.funding_percentage),
        ):
            _non_negative(name, value)
        if not self.source.strip():
            raise ValueError("execution cost source cannot be empty")

    @property
    def total_percentage(self) -> float:
        return (
            self.entry_fee_percentage
            + self.exit_fee_percentage
            + self.spread_percentage
            + self.entry_slippage_percentage
            + self.exit_slippage_percentage
            + self.funding_percentage
        )


@dataclass(frozen=True, slots=True)
class TargetObstacleEvidence:
    """Nearest opposing structure for one canonical target role."""

    target_role: TargetRole
    obstacle_price: float
    structure_kind: str
    source: str
    relation: TargetObstacleRelation
    clearance_buffer_percentage: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.obstacle_price) or self.obstacle_price <= 0.0:
            raise ValueError("obstacle price must be finite and positive")
        if not self.structure_kind.strip():
            raise ValueError("structure kind cannot be empty")
        if not self.source.strip():
            raise ValueError("obstacle source cannot be empty")
        _non_negative("clearance buffer percentage", self.clearance_buffer_percentage)


__all__ = [
    "ExecutionCostEstimate",
    "TargetObstacleEvidence",
    "TargetObstacleRelation",
]
