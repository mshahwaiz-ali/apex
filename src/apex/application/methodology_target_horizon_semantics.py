"""Interpret targets and holding horizon without universal percentage assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class TargetHorizonSemantics:
    """Truthful target ambition and duration interpretation."""

    target_count: int
    maximum_projected_move_percentage: float | None
    has_double_digit_target: bool
    universal_target_applied: bool
    target_interpretation: str
    duration_available: bool
    hold_category: str | None
    expected_hold_min_seconds: int | None
    expected_hold_max_seconds: int | None
    expected_bars: int | None
    setup_expiry_bars: int | None
    duration_interpretation: str


def derive_target_horizon_semantics(
    methodology: MethodologySnapshot,
) -> TargetHorizonSemantics:
    """Describe structure-derived targets and setup-derived holding expectations."""

    projected_moves = tuple(
        target.expected_move_percentage for target in methodology.targets
    )
    maximum_move = max(projected_moves) if projected_moves else None
    has_double_digit_target = maximum_move is not None and maximum_move >= 10.0
    if not projected_moves:
        target_interpretation = "no canonical target projection is available"
    elif has_double_digit_target:
        target_interpretation = (
            "a 10% or larger target exists because current target geometry supports it; "
            "it is not a universal objective"
        )
    else:
        target_interpretation = (
            "projected movement is below 10%; supported structure takes precedence over "
            "an arbitrary percentage objective"
        )

    duration = methodology.duration
    duration_available = duration is not None
    if duration is None:
        duration_interpretation = (
            "holding duration is unavailable and must not be inferred from strategy name, "
            "management-policy count, or a universal short window"
        )
        hold_category = None
        hold_min = None
        hold_max = None
        expected_bars = None
        expiry_bars = None
    else:
        duration_interpretation = (
            "holding duration is setup-derived from canonical timing metadata and remains "
            "an expectation rather than a guaranteed completion time"
        )
        hold_category = duration.category.value
        hold_min = duration.expected_hold_min_seconds
        hold_max = duration.expected_hold_max_seconds
        expected_bars = duration.expected_bars
        expiry_bars = duration.setup_expiry_bars

    return TargetHorizonSemantics(
        target_count=len(methodology.targets),
        maximum_projected_move_percentage=maximum_move,
        has_double_digit_target=has_double_digit_target,
        universal_target_applied=False,
        target_interpretation=target_interpretation,
        duration_available=duration_available,
        hold_category=hold_category,
        expected_hold_min_seconds=hold_min,
        expected_hold_max_seconds=hold_max,
        expected_bars=expected_bars,
        setup_expiry_bars=expiry_bars,
        duration_interpretation=duration_interpretation,
    )


def target_horizon_semantics_payload(
    semantics: TargetHorizonSemantics,
) -> dict[str, Any]:
    """Serialize target ambition and duration meaning."""

    return {
        "target_count": semantics.target_count,
        "maximum_projected_move_percentage": semantics.maximum_projected_move_percentage,
        "has_double_digit_target": semantics.has_double_digit_target,
        "universal_target_applied": semantics.universal_target_applied,
        "target_interpretation": semantics.target_interpretation,
        "duration_available": semantics.duration_available,
        "hold_category": semantics.hold_category,
        "expected_hold_min_seconds": semantics.expected_hold_min_seconds,
        "expected_hold_max_seconds": semantics.expected_hold_max_seconds,
        "expected_bars": semantics.expected_bars,
        "setup_expiry_bars": semantics.setup_expiry_bars,
        "duration_interpretation": semantics.duration_interpretation,
    }


__all__ = [
    "TargetHorizonSemantics",
    "derive_target_horizon_semantics",
    "target_horizon_semantics_payload",
]
