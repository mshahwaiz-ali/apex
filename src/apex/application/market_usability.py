"""Canonical market-usability classification from existing analysis metadata."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MarketUsabilityState(StrEnum):
    USABLE = "usable"
    USABLE_WITH_CAUTION = "usable_with_caution"
    UNUSABLE = "unusable"
    DATA_INCOMPLETE = "data_incomplete"


@dataclass(frozen=True, slots=True)
class MarketUsabilityAssessment:
    state: MarketUsabilityState
    score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("market usability score must be between zero and one")
        if not self.reasons:
            raise ValueError("market usability assessment requires reasons")
        for name, values in (
            ("reasons", self.reasons),
            ("warnings", self.warnings),
            ("missing inputs", self.missing_inputs),
        ):
            if any(not item.strip() for item in values):
                raise ValueError(f"market usability {name} cannot contain blanks")
            if len(set(values)) != len(values):
                raise ValueError(f"market usability {name} must not contain duplicates")


_DEFAULT_MAX_SPREAD_PERCENTAGE = 0.35
_DEFAULT_CAUTION_SPREAD_PERCENTAGE = 0.15


def classify_market_usability(
    data_quality_by_timeframe: Mapping[str, Mapping[str, Any]],
    *,
    maximum_spread_percentage: float = _DEFAULT_MAX_SPREAD_PERCENTAGE,
    caution_spread_percentage: float = _DEFAULT_CAUTION_SPREAD_PERCENTAGE,
) -> MarketUsabilityAssessment:
    """Classify existing frame-quality observations without changing trade approval."""

    if not data_quality_by_timeframe:
        return MarketUsabilityAssessment(
            state=MarketUsabilityState.DATA_INCOMPLETE,
            score=0.0,
            reasons=("no timeframe data-quality observations are available",),
            missing_inputs=("timeframe_data_quality",),
        )

    warnings: list[str] = []
    missing: list[str] = []
    stale_frames: list[str] = []
    confidence_values: list[float] = []
    spread_values: list[float] = []

    for timeframe, quality in data_quality_by_timeframe.items():
        if bool(quality.get("is_stale", False)):
            stale_frames.append(timeframe)
        confidence = quality.get("data_confidence")
        if isinstance(confidence, int | float) and math.isfinite(float(confidence)):
            confidence_values.append(max(0.0, min(1.0, float(confidence))))
        else:
            missing.append(f"{timeframe}:data_confidence")
        spread = _spread_value(quality)
        if spread is None:
            missing.append(f"{timeframe}:spread")
        else:
            spread_values.append(spread)
        if quality.get("exchange_tick_size") is None:
            missing.append(f"{timeframe}:tick_size")
        if quality.get("exchange_step_size") is None:
            missing.append(f"{timeframe}:step_size")

    if stale_frames:
        return MarketUsabilityAssessment(
            state=MarketUsabilityState.UNUSABLE,
            score=0.0,
            reasons=(f"stale data on timeframes: {', '.join(sorted(stale_frames))}",),
            warnings=tuple(sorted(set(warnings))),
            missing_inputs=tuple(sorted(set(missing))),
        )

    worst_spread = max(spread_values, default=0.0)
    if worst_spread > maximum_spread_percentage:
        return MarketUsabilityAssessment(
            state=MarketUsabilityState.UNUSABLE,
            score=0.0,
            reasons=(
                f"spread {worst_spread:.4f}% exceeds maximum {maximum_spread_percentage:.4f}%",
            ),
            missing_inputs=tuple(sorted(set(missing))),
        )

    average_confidence = (
        sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    )
    if worst_spread > caution_spread_percentage:
        warnings.append(f"spread is elevated at {worst_spread:.4f}%")
    if average_confidence < 0.75:
        warnings.append(f"average data confidence is {average_confidence:.2f}")
    if missing:
        warnings.append("some execution-quality metadata is unavailable")

    state = MarketUsabilityState.USABLE_WITH_CAUTION if warnings else MarketUsabilityState.USABLE
    score = max(0.0, min(1.0, average_confidence - min(worst_spread, 1.0) * 0.25))
    reason = (
        "market data is current and execution quality is acceptable"
        if state is MarketUsabilityState.USABLE
        else "market remains usable with measurable cautions"
    )
    return MarketUsabilityAssessment(
        state=state,
        score=score,
        reasons=(reason,),
        warnings=tuple(sorted(set(warnings))),
        missing_inputs=tuple(sorted(set(missing))),
    )


def market_usability_payload(assessment: MarketUsabilityAssessment) -> dict[str, Any]:
    return {
        "state": assessment.state.value,
        "score": assessment.score,
        "reasons": list(assessment.reasons),
        "warnings": list(assessment.warnings),
        "missing_inputs": list(assessment.missing_inputs),
    }


def _spread_value(quality: Mapping[str, Any]) -> float | None:
    for key in ("order_book_spread_percentage", "spread_percentage"):
        value = quality.get(key)
        if isinstance(value, int | float) and math.isfinite(float(value)):
            return max(0.0, float(value))
    return None


__all__ = [
    "MarketUsabilityAssessment",
    "MarketUsabilityState",
    "classify_market_usability",
    "market_usability_payload",
]
