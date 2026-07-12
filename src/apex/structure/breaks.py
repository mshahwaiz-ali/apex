"""Break-of-structure and change-of-character detection."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ChangeOfCharacter,
    ConfirmationStatus,
    PivotStatus,
    StructureBreak,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
)

_BULLISH_TRENDS = {
    TrendDirection.WEAK_BULLISH,
    TrendDirection.BULLISH,
    TrendDirection.STRONG_BULLISH,
}
_BEARISH_TRENDS = {
    TrendDirection.WEAK_BEARISH,
    TrendDirection.BEARISH,
    TrendDirection.STRONG_BEARISH,
}


def detect_structure_breaks(
    candles: Sequence[Candle],
    swings: Sequence[SwingPoint],
    *,
    minimum_close_distance: float = 0.0,
    strong_close_distance: float = 0.005,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> tuple[StructureBreak, ...]:
    """Detect the first meaningful breach of each confirmed pivot level."""

    if not math.isfinite(minimum_close_distance) or not math.isfinite(
        strong_close_distance
    ):
        raise ValueError("break-distance thresholds must be finite")
    if minimum_close_distance < 0 or strong_close_distance < minimum_close_distance:
        raise ValueError("break-distance thresholds are invalid")

    usable = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    events: list[StructureBreak] = []

    for swing in swings:
        if swing.status is not PivotStatus.CONFIRMED or swing.index >= len(usable) - 1:
            continue
        event = _first_break(
            usable,
            swing,
            minimum_close_distance=minimum_close_distance,
            strong_close_distance=strong_close_distance,
        )
        if event is not None:
            events.append(event)

    unique: dict[tuple[int, BreakDirection, float], StructureBreak] = {}
    for event in events:
        key = (event.candle_index, event.direction, event.broken_level)
        unique.setdefault(key, event)
    return tuple(sorted(unique.values(), key=lambda item: (item.candle_index, item.direction.value)))


def detect_changes_of_character(
    trend: TrendAnalysis,
    breaks: Sequence[StructureBreak],
) -> tuple[ChangeOfCharacter, ...]:
    """Return opposing confirmed breaks that disrupt an established trend."""

    if trend.direction in _BULLISH_TRENDS:
        opposing = BreakDirection.BEARISH
    elif trend.direction in _BEARISH_TRENDS:
        opposing = BreakDirection.BULLISH
    else:
        return ()

    events = []
    for event in breaks:
        if event.direction is not opposing:
            continue
        if event.confirmation is not ConfirmationStatus.CONFIRMED:
            continue
        if event.quality not in {BreakQuality.VALID, BreakQuality.STRONG}:
            continue
        events.append(
            ChangeOfCharacter(
                prior_trend=trend.direction,
                break_event=event,
                confirmation=ConfirmationStatus.CONFIRMED,
                evidence=("opposing close broke a confirmed structural pivot",),
            )
        )
    return tuple(events)


def _first_break(
    candles: Sequence[Candle],
    swing: SwingPoint,
    *,
    minimum_close_distance: float,
    strong_close_distance: float,
) -> StructureBreak | None:
    bullish = swing.kind is SwingType.HIGH
    direction = BreakDirection.BULLISH if bullish else BreakDirection.BEARISH
    level = swing.price

    for index in range(swing.index + 1, len(candles)):
        candle = candles[index]
        wick_distance = (candle.high - level) if bullish else (level - candle.low)
        if wick_distance <= 0:
            continue

        close_distance_raw = (candle.close - level) if bullish else (level - candle.close)
        close_distance = close_distance_raw / level
        wick_penetration = wick_distance / level
        closed_beyond = close_distance_raw > 0
        is_active = not candle.is_closed

        if not closed_beyond:
            quality = BreakQuality.WICK_ONLY
            confirmation = ConfirmationStatus.DEVELOPING if is_active else ConfirmationStatus.REJECTED
            evidence = ("wick breached level but close did not sustain beyond it",)
        elif close_distance < minimum_close_distance:
            quality = BreakQuality.WEAK
            confirmation = ConfirmationStatus.DEVELOPING if is_active else ConfirmationStatus.REJECTED
            evidence = ("close penetration was below the configured threshold",)
        else:
            quality = (
                BreakQuality.STRONG
                if close_distance >= strong_close_distance
                else BreakQuality.VALID
            )
            confirmation = (
                ConfirmationStatus.DEVELOPING if is_active else ConfirmationStatus.CONFIRMED
            )
            evidence = ("candle closed beyond a confirmed structural pivot",)

        return StructureBreak(
            direction=direction,
            broken_swing=swing,
            candle_index=index,
            candle_time=candle.open_time,
            broken_level=level,
            close_distance=close_distance,
            wick_penetration=wick_penetration,
            quality=quality,
            confirmation=confirmation,
            evidence=evidence,
            warnings=("active candle result is provisional",) if is_active else (),
        )
    return None
