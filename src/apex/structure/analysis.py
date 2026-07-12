"""High-level deterministic market-structure orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.breaks import detect_changes_of_character, detect_structure_breaks
from apex.structure.contracts import StructureAnalysisResult
from apex.structure.levels import derive_structure_levels
from apex.structure.ranges import detect_range
from apex.structure.swings import detect_swings
from apex.structure.trend import classify_trend


def analyze_structure(
    candles: Sequence[Candle],
    *,
    left_window: int = 2,
    right_window: int = 2,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> StructureAnalysisResult:
    """Run the Phase 3 structure pipeline in a fixed execution order."""

    usable = prepare_candles(
        candles,
        minimum_candles=left_window + 1,
        active_candle_policy=active_candle_policy,
    )
    swings = detect_swings(
        usable,
        left_window=left_window,
        right_window=right_window,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    trend = classify_trend(swings)
    breaks = detect_structure_breaks(
        usable,
        swings,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    changes = detect_changes_of_character(trend, breaks)
    detected_range = (
        detect_range(
            usable,
            active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
        )
        if len(usable) >= 21
        else None
    )
    levels = derive_structure_levels(swings, usable)
    return StructureAnalysisResult(
        swings=swings,
        trend=trend,
        breaks=breaks,
        changes_of_character=changes,
        ranges=(detected_range,) if detected_range is not None else (),
        levels=levels,
    )
