"""Trap and failed-breakout foundations tied to liquidity events."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.liquidity.contracts import (
    LiquiditySide,
    LiquiditySweep,
    SweepClassification,
    TrapEvent,
    TrapType,
)
from apex.structure.contracts import ConfirmationStatus


def detect_traps(
    candles: Sequence[Candle],
    sweeps: Sequence[LiquiditySweep],
    *,
    follow_through_candles: int = 2,
    maximum_chase_distance: float = 0.01,
) -> tuple[TrapEvent, ...]:
    """Detect traps and failed breakouts only from known liquidity events."""

    if follow_through_candles < 1:
        raise ValueError("follow_through_candles must be at least 1")
    if not math.isfinite(maximum_chase_distance) or maximum_chase_distance < 0:
        raise ValueError("maximum_chase_distance must be finite and non-negative")

    events: list[TrapEvent] = []
    for sweep in sweeps:
        if sweep.candle_index >= len(candles):
            continue

        source = candles[sweep.candle_index]
        following = candles[
            sweep.candle_index + 1 : sweep.candle_index + 1 + follow_through_candles
        ]
        buy_side = sweep.zone.side is LiquiditySide.BUY_SIDE
        invalidation = (
            (f"close above {sweep.zone.high}",) if buy_side else (f"close below {sweep.zone.low}",)
        )

        if sweep.classification is SweepClassification.CONFIRMED_SWEEP:
            recovered = (
                any(candle.close < source.close for candle in following)
                if buy_side
                else any(candle.close > source.close for candle in following)
            )
            if recovered:
                events.append(
                    TrapEvent(
                        kind=TrapType.BULL_TRAP if buy_side else TrapType.BEAR_TRAP,
                        candle_index=sweep.candle_index,
                        candle_time=sweep.candle_time,
                        zone=sweep.zone,
                        sweep=sweep,
                        confirmation=ConfirmationStatus.CONFIRMED,
                        evidence=(
                            "liquidity breach closed back inside the zone",
                            "subsequent candle confirmed rejection follow-through",
                        ),
                        invalidation=invalidation,
                    )
                )
            else:
                events.append(
                    TrapEvent(
                        kind=TrapType.BREAKOUT_REJECTION,
                        candle_index=sweep.candle_index,
                        candle_time=sweep.candle_time,
                        zone=sweep.zone,
                        sweep=sweep,
                        confirmation=ConfirmationStatus.DEVELOPING,
                        evidence=(
                            "liquidity breach closed back inside the zone",
                            "rejection follow-through is not confirmed yet",
                        ),
                        invalidation=invalidation,
                    )
                )
            continue

        if sweep.classification is not SweepClassification.SIMPLE_BREAKOUT:
            continue

        failed = (
            any(candle.close <= sweep.zone.high for candle in following)
            if buy_side
            else any(candle.close >= sweep.zone.low for candle in following)
        )
        if failed:
            events.append(
                TrapEvent(
                    kind=TrapType.FAILED_BREAKOUT,
                    candle_index=sweep.candle_index,
                    candle_time=sweep.candle_time,
                    zone=sweep.zone,
                    sweep=sweep,
                    confirmation=ConfirmationStatus.CONFIRMED,
                    evidence=(
                        "breakout initially closed beyond liquidity",
                        "subsequent close returned inside the broken zone",
                    ),
                    invalidation=invalidation,
                )
            )

        boundary = sweep.zone.high if buy_side else sweep.zone.low
        close_distance = (
            (source.close - boundary) / boundary
            if buy_side
            else (boundary - source.close) / boundary
        )
        if close_distance > maximum_chase_distance:
            events.append(
                TrapEvent(
                    kind=TrapType.LATE_CHASE_RISK,
                    candle_index=sweep.candle_index,
                    candle_time=sweep.candle_time,
                    zone=sweep.zone,
                    sweep=sweep,
                    confirmation=ConfirmationStatus.CONFIRMED,
                    evidence=("breakout close is materially extended from the liquidity boundary",),
                    invalidation=("price retests the breakout boundary before entry",),
                )
            )

    return tuple(sorted(events, key=lambda item: (item.candle_index, item.kind.value)))
