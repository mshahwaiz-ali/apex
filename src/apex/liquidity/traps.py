"""Trap and failed-breakout foundations tied to liquidity events."""

from __future__ import annotations

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
) -> tuple[TrapEvent, ...]:
    """Detect bull/bear traps only from confirmed sweep or rejection events."""

    if follow_through_candles < 1:
        raise ValueError("follow_through_candles must be at least 1")

    events: list[TrapEvent] = []
    for sweep in sweeps:
        if sweep.classification is not SweepClassification.CONFIRMED_SWEEP:
            continue
        if sweep.candle_index >= len(candles):
            continue

        source = candles[sweep.candle_index]
        following = candles[
            sweep.candle_index + 1 : sweep.candle_index + 1 + follow_through_candles
        ]
        buy_side = sweep.zone.side is LiquiditySide.BUY_SIDE
        recovered = (
            any(candle.close < source.close for candle in following)
            if buy_side
            else any(candle.close > source.close for candle in following)
        )
        if not recovered:
            continue

        kind = TrapType.BULL_TRAP if buy_side else TrapType.BEAR_TRAP
        invalidation = (
            (f"close above {sweep.zone.high}",)
            if buy_side
            else (f"close below {sweep.zone.low}",)
        )
        events.append(
            TrapEvent(
                kind=kind,
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

    return tuple(sorted(events, key=lambda item: (item.candle_index, item.kind.value)))
