"""Read-only spread-deterioration diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class SpreadDeteriorationState(StrEnum):
    """Execution-quality state derived from baseline and current spread."""

    HEALTHY = "healthy"
    DETERIORATING = "deteriorating"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class SpreadDeteriorationPolicy:
    """Explicit relative and absolute spread limits."""

    deterioration_multiple: float = 1.5
    blocking_multiple: float = 2.5
    maximum_spread_fraction: float = 0.003

    def __post_init__(self) -> None:
        for name, value in (
            ("deterioration multiple", self.deterioration_multiple),
            ("blocking multiple", self.blocking_multiple),
            ("maximum spread fraction", self.maximum_spread_fraction),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.deterioration_multiple >= self.blocking_multiple:
            raise ValueError("deterioration multiple must be below blocking multiple")


@dataclass(frozen=True, slots=True)
class SpreadDeteriorationObservation:
    """Baseline and current bid/ask spread observations."""

    baseline_spread_fraction: float
    current_spread_fraction: float

    def __post_init__(self) -> None:
        for name, value in (
            ("baseline spread fraction", self.baseline_spread_fraction),
            ("current spread fraction", self.current_spread_fraction),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.baseline_spread_fraction == 0:
            raise ValueError("baseline spread fraction must be positive")


@dataclass(frozen=True, slots=True)
class SpreadDeteriorationAudit:
    """Read-only execution-quality spread result."""

    state: SpreadDeteriorationState
    spread_multiple: float
    current_spread_fraction: float

    @property
    def blocks_execution(self) -> bool:
        return self.state is SpreadDeteriorationState.BLOCKING


def audit_spread_deterioration(
    observation: SpreadDeteriorationObservation,
    *,
    policy: SpreadDeteriorationPolicy,
) -> SpreadDeteriorationAudit:
    """Classify spread widening without changing execution behavior."""

    multiple = observation.current_spread_fraction / observation.baseline_spread_fraction
    if (
        multiple >= policy.blocking_multiple
        or observation.current_spread_fraction >= policy.maximum_spread_fraction
    ):
        state = SpreadDeteriorationState.BLOCKING
    elif multiple >= policy.deterioration_multiple:
        state = SpreadDeteriorationState.DETERIORATING
    else:
        state = SpreadDeteriorationState.HEALTHY

    return SpreadDeteriorationAudit(
        state=state,
        spread_multiple=multiple,
        current_spread_fraction=observation.current_spread_fraction,
    )
