"""Explainable trend classification from confirmed structural pivots."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise

from apex.structure.contracts import (
    PivotStatus,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)


def classify_trend(
    swings: Sequence[SwingPoint],
    *,
    minimum_pairs: int = 2,
    strong_persistence: float = 0.8,
    weak_persistence: float = 0.5,
    equality_tolerance: float = 0.0,
) -> TrendAnalysis:
    """Classify trend from higher/lower pivot sequences with explicit evidence."""

    if minimum_pairs < 1:
        raise ValueError("minimum_pairs must be at least 1")
    if not all(
        math.isfinite(value) for value in (strong_persistence, weak_persistence, equality_tolerance)
    ):
        raise ValueError("trend thresholds must be finite")
    if not 0 <= weak_persistence <= strong_persistence <= 1:
        raise ValueError("persistence thresholds must satisfy 0 <= weak <= strong <= 1")
    if equality_tolerance < 0:
        raise ValueError("equality_tolerance cannot be negative")

    confirmed = tuple(item for item in swings if item.status is PivotStatus.CONFIRMED)
    highs = tuple(item for item in confirmed if item.kind is SwingType.HIGH)
    lows = tuple(item for item in confirmed if item.kind is SwingType.LOW)

    high_moves = _classify_moves(highs, equality_tolerance)
    low_moves = _classify_moves(lows, equality_tolerance)
    higher_highs = high_moves.count(1)
    lower_highs = high_moves.count(-1)
    equal_highs = high_moves.count(0)
    higher_lows = low_moves.count(1)
    lower_lows = low_moves.count(-1)
    equal_lows = low_moves.count(0)

    directional_moves = higher_highs + higher_lows + lower_highs + lower_lows
    bullish_moves = higher_highs + higher_lows
    bearish_moves = lower_highs + lower_lows
    dominant = max(bullish_moves, bearish_moves)
    persistence = dominant / directional_moves if directional_moves else 0.0

    evidence = TrendEvidence(
        higher_highs=higher_highs,
        higher_lows=higher_lows,
        lower_highs=lower_highs,
        lower_lows=lower_lows,
        equal_highs=equal_highs,
        equal_lows=equal_lows,
        persistence=persistence,
        notes=_notes(highs, lows, bullish_moves, bearish_moves),
    )

    available_pairs = len(high_moves) + len(low_moves)
    if available_pairs < minimum_pairs:
        return TrendAnalysis(
            TrendDirection.UNCERTAIN,
            persistence,
            evidence,
            ("insufficient confirmed pivot pairs",),
        )

    direction = _direction(
        bullish_moves,
        bearish_moves,
        equal_highs + equal_lows,
        persistence,
        strong_persistence,
        weak_persistence,
    )
    return TrendAnalysis(direction, persistence, evidence)


def _classify_moves(swings: Sequence[SwingPoint], tolerance: float) -> tuple[int, ...]:
    moves: list[int] = []
    for previous, current in pairwise(swings):
        scale = max(abs(previous.price), abs(current.price), 1.0)
        difference = current.price - previous.price
        if abs(difference) <= tolerance * scale:
            moves.append(0)
        elif difference > 0:
            moves.append(1)
        else:
            moves.append(-1)
    return tuple(moves)


def _direction(
    bullish: int,
    bearish: int,
    equal: int,
    persistence: float,
    strong_threshold: float,
    weak_threshold: float,
) -> TrendDirection:
    if bullish == bearish:
        return TrendDirection.RANGE if equal > 0 or bullish == 0 else TrendDirection.TRANSITION

    conflict = min(bullish, bearish) > 0
    if bullish > bearish:
        if persistence >= strong_threshold and not conflict:
            return TrendDirection.STRONG_BULLISH
        if persistence >= weak_threshold:
            return TrendDirection.BULLISH
        return TrendDirection.WEAK_BULLISH

    if persistence >= strong_threshold and not conflict:
        return TrendDirection.STRONG_BEARISH
    if persistence >= weak_threshold:
        return TrendDirection.BEARISH
    return TrendDirection.WEAK_BEARISH


def _notes(
    highs: Sequence[SwingPoint],
    lows: Sequence[SwingPoint],
    bullish: int,
    bearish: int,
) -> tuple[str, ...]:
    notes = [f"{len(highs)} confirmed highs", f"{len(lows)} confirmed lows"]
    if bullish:
        notes.append(f"{bullish} bullish structural advances")
    if bearish:
        notes.append(f"{bearish} bearish structural declines")
    return tuple(notes)
