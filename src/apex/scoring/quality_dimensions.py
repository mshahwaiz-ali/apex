"""Independent setup, execution, target, and risk quality dimensions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.strategies.contracts import RawQualityMetrics


def _bounded(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be finite and between zero and 100")


@dataclass(frozen=True, slots=True)
class CandidateQualityDimensions:
    """Explain candidate quality without treating setup quality as executability."""

    setup_quality: float
    execution_quality: float
    target_quality: float
    risk_quality: float
    overall_trade_quality: float

    def __post_init__(self) -> None:
        for name in (
            "setup_quality",
            "execution_quality",
            "target_quality",
            "risk_quality",
            "overall_trade_quality",
        ):
            _bounded(name.replace("_", " "), getattr(self, name))


def derive_quality_dimensions(metrics: RawQualityMetrics) -> CandidateQualityDimensions:
    """Derive transparent dimensions from existing normalized strategy metrics."""

    setup_quality = 100.0 * (
        metrics.trend_alignment * 0.28
        + metrics.structure_quality * 0.32
        + metrics.momentum_quality * 0.20
        + metrics.volume_quality * 0.10
        + metrics.liquidity_quality * 0.10
    )
    execution_quality = 100.0 * (
        metrics.entry_quality * 0.70 + (1.0 - metrics.extension_penalty) * 0.30
    )
    target_quality = metrics.target_space_quality * 100.0
    risk_quality = 100.0 * (
        metrics.structure_quality * 0.45
        + metrics.entry_quality * 0.35
        + (1.0 - metrics.conflict_penalty) * 0.20
    )
    overall_trade_quality = (
        setup_quality * 0.40
        + execution_quality * 0.25
        + target_quality * 0.20
        + risk_quality * 0.15
    )
    return CandidateQualityDimensions(
        setup_quality=round(setup_quality, 4),
        execution_quality=round(execution_quality, 4),
        target_quality=round(target_quality, 4),
        risk_quality=round(risk_quality, 4),
        overall_trade_quality=round(overall_trade_quality, 4),
    )


__all__ = ["CandidateQualityDimensions", "derive_quality_dimensions"]
