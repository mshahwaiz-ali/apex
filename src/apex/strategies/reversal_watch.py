"""Objective reversal-watch evidence without automatic trade creation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.domain.models import Candle
from apex.strategies.contracts import TradeDirection


class ReversalWatchState(StrEnum):
    """Non-executable reversal observation state."""

    NONE = "none"
    WATCH = "watch"
    TRIGGERED = "triggered"


@dataclass(frozen=True, slots=True)
class ReversalWatch:
    """Measured reversal evidence and trigger state."""

    state: ReversalWatchState
    reversal_direction: TradeDirection
    swing_failure: bool
    wick_rejection: bool
    recovery_present: bool
    reclaim_level: float
    reclaim_complete: bool
    trigger_required: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.reclaim_level) or self.reclaim_level <= 0:
            raise ValueError("reclaim level must be positive and finite")
        if self.state is ReversalWatchState.TRIGGERED and not self.reclaim_complete:
            raise ValueError("triggered reversal watch requires completed reclaim")
        if not self.reasons:
            raise ValueError("reversal watch requires explanatory reasons")

    @property
    def may_create_reversal_candidate(self) -> bool:
        """Only completed triggers may be promoted by a reversal strategy."""

        return self.state is ReversalWatchState.TRIGGERED


def classify_reversal_watch(
    *,
    candles: tuple[Candle, ...],
    exhausted_direction: TradeDirection,
    reclaim_level: float,
    atr: float,
) -> ReversalWatch:
    """Classify failed continuation and reclaim evidence."""

    if len(candles) < 3:
        raise ValueError("reversal watch requires at least three candles")
    if not math.isfinite(reclaim_level) or reclaim_level <= 0:
        raise ValueError("reclaim level must be positive and finite")
    if not math.isfinite(atr) or atr <= 0:
        raise ValueError("ATR must be positive and finite")

    closed = tuple(candle for candle in candles if candle.is_closed)
    if len(closed) < 3:
        raise ValueError("reversal watch requires at least three closed candles")
    recent = closed[-3:]
    latest = recent[-1]
    previous = recent[-2]
    reversal_direction = (
        TradeDirection.LONG if exhausted_direction is TradeDirection.SHORT else TradeDirection.SHORT
    )

    if reversal_direction is TradeDirection.LONG:
        swing_failure = latest.low > previous.low
        lower_wick = min(latest.open, latest.close) - latest.low
        body = abs(latest.close - latest.open)
        wick_rejection = lower_wick >= max(body, atr * 0.20)
        recovery_present = latest.close > latest.open and latest.close > previous.close
        reclaim_complete = latest.close > reclaim_level
    else:
        swing_failure = latest.high < previous.high
        upper_wick = latest.high - max(latest.open, latest.close)
        body = abs(latest.close - latest.open)
        wick_rejection = upper_wick >= max(body, atr * 0.20)
        recovery_present = latest.close < latest.open and latest.close < previous.close
        reclaim_complete = latest.close < reclaim_level

    watch_present = swing_failure or wick_rejection or recovery_present
    triggered = swing_failure and recovery_present and reclaim_complete
    state = (
        ReversalWatchState.TRIGGERED
        if triggered
        else ReversalWatchState.WATCH
        if watch_present
        else ReversalWatchState.NONE
    )
    reasons = (
        (
            "directional swing failure is present"
            if swing_failure
            else "directional swing failure is not confirmed"
        ),
        (
            "rejection wick meets the ATR-aware threshold"
            if wick_rejection
            else "rejection wick is insufficient"
        ),
        (
            "opposite-direction recovery candle is present"
            if recovery_present
            else "opposite-direction recovery is not confirmed"
        ),
        (
            "reclaim trigger is complete"
            if reclaim_complete
            else "reclaim trigger remains incomplete"
        ),
    )
    return ReversalWatch(
        state=state,
        reversal_direction=reversal_direction,
        swing_failure=swing_failure,
        wick_rejection=wick_rejection,
        recovery_present=recovery_present,
        reclaim_level=reclaim_level,
        reclaim_complete=reclaim_complete,
        trigger_required=not triggered,
        reasons=reasons,
    )


__all__ = [
    "ReversalWatch",
    "ReversalWatchState",
    "classify_reversal_watch",
]
