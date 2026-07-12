"""Deterministic liquidity sweep and breach classification."""

from __future__ import annotations

import math
from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.liquidity.contracts import (
    LiquiditySide,
    LiquiditySweep,
    LiquidityZone,
    SweepClassification,
)
from apex.structure.contracts import BreakDirection, ConfirmationStatus


def detect_liquidity_sweeps(
    candles: Sequence[Candle],
    zones: Sequence[LiquidityZone],
    *,
    minimum_penetration: float = 0.0,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> tuple[LiquiditySweep, ...]:
    """Classify the first post-zone breach as sweep, breakout, or unresolved."""

    if not math.isfinite(minimum_penetration) or minimum_penetration < 0:
        raise ValueError("minimum_penetration must be finite and non-negative")
    usable = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    events: list[LiquiditySweep] = []
    for zone in zones:
        start = zone.last_touch_index + 1
        for index in range(start, len(usable)):
            candle = usable[index]
            event = _classify_breach(candle, index, zone, minimum_penetration)
            if event is not None:
                events.append(event)
                break
    return tuple(sorted(events, key=lambda item: (item.candle_index, item.zone.side.value)))


def _classify_breach(
    candle: Candle,
    index: int,
    zone: LiquidityZone,
    minimum_penetration: float,
) -> LiquiditySweep | None:
    buy_side = zone.side is LiquiditySide.BUY_SIDE
    boundary = zone.high if buy_side else zone.low
    extreme = candle.high if buy_side else candle.low
    raw_penetration = extreme - boundary if buy_side else boundary - extreme
    if raw_penetration <= 0:
        return None

    penetration = raw_penetration / boundary
    close_inside = candle.close <= zone.high if buy_side else candle.close >= zone.low
    close_recovery = (
        (boundary - candle.close) / boundary
        if buy_side
        else (candle.close - boundary) / boundary
    )
    is_active = not candle.is_closed
    direction = BreakDirection.BULLISH if buy_side else BreakDirection.BEARISH

    if penetration < minimum_penetration:
        classification = SweepClassification.UNRESOLVED_BREACH
        confirmation = ConfirmationStatus.REJECTED
        evidence = ("zone penetration was below the configured threshold",)
    elif close_inside:
        classification = (
            SweepClassification.DEVELOPING_SWEEP
            if is_active
            else SweepClassification.CONFIRMED_SWEEP
        )
        confirmation = (
            ConfirmationStatus.DEVELOPING if is_active else ConfirmationStatus.CONFIRMED
        )
        evidence = ("price breached liquidity and closed back inside the zone",)
    elif is_active:
        classification = SweepClassification.UNRESOLVED_BREACH
        confirmation = ConfirmationStatus.DEVELOPING
        evidence = ("active candle remains beyond the liquidity zone",)
    else:
        classification = SweepClassification.SIMPLE_BREAKOUT
        confirmation = ConfirmationStatus.CONFIRMED
        evidence = ("closed candle sustained beyond the liquidity zone",)

    return LiquiditySweep(
        zone=zone,
        direction=direction,
        candle_index=index,
        candle_time=candle.open_time,
        penetration=penetration,
        close_recovery=close_recovery,
        classification=classification,
        confirmation=confirmation,
        evidence=evidence,
        warnings=("active candle result is provisional",) if is_active else (),
    )
