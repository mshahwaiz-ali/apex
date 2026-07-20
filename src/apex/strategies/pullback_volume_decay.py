"""Read-only pullback-volume decay diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class PullbackVolumeState(StrEnum):
    """Continuation quality inferred from impulse and pullback volume."""

    HEALTHY_DECAY = "healthy_decay"
    MIXED = "mixed"
    EXPANDING_AGAINST = "expanding_against"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class PullbackVolumePolicy:
    """Thresholds for comparing pullback participation with impulse participation."""

    healthy_maximum_ratio: float = 0.70
    adverse_minimum_ratio: float = 1.05
    minimum_impulse_volume: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (
            ("healthy maximum ratio", self.healthy_maximum_ratio),
            ("adverse minimum ratio", self.adverse_minimum_ratio),
            ("minimum impulse volume", self.minimum_impulse_volume),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.healthy_maximum_ratio >= self.adverse_minimum_ratio:
            raise ValueError("healthy ratio must be below adverse ratio")


@dataclass(frozen=True, slots=True)
class PullbackVolumeObservation:
    """Normalized impulse and pullback volume aggregates."""

    impulse_volume: float
    pullback_volume: float
    impulse_bars: int
    pullback_bars: int

    def __post_init__(self) -> None:
        for name, value in (
            ("impulse volume", self.impulse_volume),
            ("pullback volume", self.pullback_volume),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.impulse_bars <= 0 or self.pullback_bars <= 0:
            raise ValueError("impulse and pullback bars must be positive")


@dataclass(frozen=True, slots=True)
class PullbackVolumeAudit:
    """Read-only pullback participation result."""

    state: PullbackVolumeState
    normalized_volume_ratio: float | None
    impulse_volume_per_bar: float
    pullback_volume_per_bar: float


def audit_pullback_volume_decay(
    observation: PullbackVolumeObservation,
    *,
    policy: PullbackVolumePolicy,
) -> PullbackVolumeAudit:
    """Classify whether pullback participation decays after the impulse."""

    impulse_per_bar = observation.impulse_volume / observation.impulse_bars
    pullback_per_bar = observation.pullback_volume / observation.pullback_bars
    if observation.impulse_volume < policy.minimum_impulse_volume or impulse_per_bar == 0:
        return PullbackVolumeAudit(
            state=PullbackVolumeState.INSUFFICIENT,
            normalized_volume_ratio=None,
            impulse_volume_per_bar=impulse_per_bar,
            pullback_volume_per_bar=pullback_per_bar,
        )

    ratio = pullback_per_bar / impulse_per_bar
    if ratio <= policy.healthy_maximum_ratio:
        state = PullbackVolumeState.HEALTHY_DECAY
    elif ratio >= policy.adverse_minimum_ratio:
        state = PullbackVolumeState.EXPANDING_AGAINST
    else:
        state = PullbackVolumeState.MIXED

    return PullbackVolumeAudit(
        state=state,
        normalized_volume_ratio=ratio,
        impulse_volume_per_bar=impulse_per_bar,
        pullback_volume_per_bar=pullback_per_bar,
    )
