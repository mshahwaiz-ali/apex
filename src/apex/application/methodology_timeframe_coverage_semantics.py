"""Audit evaluated timeframe coverage and visible data-quality degradation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis


@dataclass(frozen=True, slots=True)
class TimeframeCoverageSemantics:
    """Public coverage audit derived from the actual analysis metadata."""

    evaluated_timeframes: tuple[str, ...]
    regime_timeframes: tuple[str, ...]
    quality_timeframes: tuple[str, ...]
    missing_regime_timeframes: tuple[str, ...]
    missing_quality_timeframes: tuple[str, ...]
    stale_timeframes: tuple[str, ...]
    low_confidence_timeframes: tuple[str, ...]
    complete_coverage: bool
    degraded_coverage: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_timeframe_coverage_semantics(
    analysis: SymbolAnalysis,
    *,
    low_confidence_threshold: float = 0.75,
) -> TimeframeCoverageSemantics:
    """Compare requested/evaluated frames with regime and quality observations."""

    evaluated = tuple(analysis.evaluated_timeframes)
    regime_frames = tuple(sorted(analysis.regime_by_timeframe))
    quality_frames = tuple(sorted(analysis.data_quality_by_timeframe))
    regime_set = set(regime_frames)
    quality_set = set(quality_frames)
    missing_regime = tuple(frame for frame in evaluated if frame not in regime_set)
    missing_quality = tuple(frame for frame in evaluated if frame not in quality_set)

    stale: list[str] = []
    low_confidence: list[str] = []
    for timeframe, quality in analysis.data_quality_by_timeframe.items():
        if quality.get("is_stale") is True:
            stale.append(timeframe)
        confidence = quality.get("data_confidence")
        if (
            isinstance(confidence, int | float)
            and not isinstance(confidence, bool)
            and float(confidence) < low_confidence_threshold
        ):
            low_confidence.append(timeframe)

    complete = bool(evaluated) and not missing_regime and not missing_quality
    degraded = bool(stale or low_confidence or missing_regime or missing_quality)
    if not evaluated:
        interpretation = "no evaluated timeframes are recorded; coverage cannot be established"
    elif stale:
        interpretation = "one or more evaluated timeframes contain explicitly stale data"
    elif missing_regime or missing_quality:
        interpretation = (
            "timeframe coverage is incomplete because regime or quality metadata is missing"
        )
    elif low_confidence:
        interpretation = (
            "all evaluated timeframes are represented, but one or more have reduced data confidence"
        )
    else:
        interpretation = "all evaluated timeframes have visible regime and quality metadata"

    return TimeframeCoverageSemantics(
        evaluated_timeframes=evaluated,
        regime_timeframes=regime_frames,
        quality_timeframes=quality_frames,
        missing_regime_timeframes=missing_regime,
        missing_quality_timeframes=missing_quality,
        stale_timeframes=tuple(sorted(stale)),
        low_confidence_timeframes=tuple(sorted(low_confidence)),
        complete_coverage=complete,
        degraded_coverage=degraded,
        interpretation=interpretation,
        limitations=(
            "coverage confirms metadata presence, not analytical correctness",
            "a timeframe is not assumed healthy merely because its key exists",
            "missing frames remain missing and are not reconstructed from neighboring timeframes",
            "coverage quality does not override hard blockers or incomplete execution geometry",
        ),
    )


def timeframe_coverage_semantics_payload(
    semantics: TimeframeCoverageSemantics,
) -> dict[str, Any]:
    """Serialize timeframe coverage and degradation details."""

    return {
        "evaluated_timeframes": list(semantics.evaluated_timeframes),
        "regime_timeframes": list(semantics.regime_timeframes),
        "quality_timeframes": list(semantics.quality_timeframes),
        "missing_regime_timeframes": list(semantics.missing_regime_timeframes),
        "missing_quality_timeframes": list(semantics.missing_quality_timeframes),
        "stale_timeframes": list(semantics.stale_timeframes),
        "low_confidence_timeframes": list(semantics.low_confidence_timeframes),
        "complete_coverage": semantics.complete_coverage,
        "degraded_coverage": semantics.degraded_coverage,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "TimeframeCoverageSemantics",
    "derive_timeframe_coverage_semantics",
    "timeframe_coverage_semantics_payload",
]
