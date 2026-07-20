"""Read-only breakout-acceptance duration diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import TradeDirection


class BreakoutAcceptanceState(StrEnum):
    """Diagnostic state of price acceptance beyond a breakout level."""

    NOT_BROKEN = "not_broken"
    REJECTED = "rejected"
    PROVISIONAL = "provisional"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class BreakoutAcceptancePolicy:
    """Explicit rules for confirming breakout acceptance."""

    minimum_consecutive_closes: int = 2
    minimum_acceptance_seconds: int = 60
    maximum_reentry_fraction: float = 0.0

    def __post_init__(self) -> None:
        if self.minimum_consecutive_closes <= 0:
            raise ValueError("minimum consecutive closes must be positive")
        if self.minimum_acceptance_seconds < 0:
            raise ValueError("minimum acceptance seconds cannot be negative")
        if not math.isfinite(self.maximum_reentry_fraction):
            raise ValueError("maximum reentry fraction must be finite")
        if not 0.0 <= self.maximum_reentry_fraction <= 1.0:
            raise ValueError("maximum reentry fraction must be between zero and one")


@dataclass(frozen=True, slots=True)
class BreakoutBarObservation:
    """Normalized closed-bar evidence supplied by an existing candle adapter."""

    close: float
    high: float
    low: float
    duration_seconds: int
    closed: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("close", self.close),
            ("high", self.high),
            ("low", self.low),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.low > self.high:
            raise ValueError("bar low cannot exceed bar high")
        if not self.low <= self.close <= self.high:
            raise ValueError("bar close must lie inside the bar range")
        if self.duration_seconds <= 0:
            raise ValueError("bar duration must be positive")


@dataclass(frozen=True, slots=True)
class BreakoutAcceptanceAudit:
    """Read-only acceptance result for one breakout level."""

    direction: TradeDirection
    breakout_level: float
    state: BreakoutAcceptanceState
    consecutive_closes: int
    acceptance_seconds: int
    reentry_fraction: float
    evaluated_closed_bars: int

    @property
    def accepted(self) -> bool:
        return self.state is BreakoutAcceptanceState.ACCEPTED


def _beyond_level(
    direction: TradeDirection,
    close: float,
    breakout_level: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return close > breakout_level
    return close < breakout_level


def _touched_beyond_level(
    direction: TradeDirection,
    bar: BreakoutBarObservation,
    breakout_level: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return bar.high > breakout_level
    return bar.low < breakout_level


def _reentered_structure(
    direction: TradeDirection,
    bar: BreakoutBarObservation,
    breakout_level: float,
) -> bool:
    if direction is TradeDirection.LONG:
        return bar.close <= breakout_level
    return bar.close >= breakout_level


def audit_breakout_acceptance(
    direction: TradeDirection,
    breakout_level: float,
    bars: tuple[BreakoutBarObservation, ...],
    *,
    policy: BreakoutAcceptancePolicy,
) -> BreakoutAcceptanceAudit:
    """Measure closed-bar acceptance beyond a known structural level."""

    if not math.isfinite(breakout_level) or breakout_level <= 0:
        raise ValueError("breakout level must be positive and finite")

    closed_bars = tuple(bar for bar in bars if bar.closed)
    if not closed_bars:
        return BreakoutAcceptanceAudit(
            direction=direction,
            breakout_level=breakout_level,
            state=BreakoutAcceptanceState.NOT_BROKEN,
            consecutive_closes=0,
            acceptance_seconds=0,
            reentry_fraction=0.0,
            evaluated_closed_bars=0,
        )

    touched = any(_touched_beyond_level(direction, bar, breakout_level) for bar in closed_bars)
    beyond_count = sum(
        1 for bar in closed_bars if _beyond_level(direction, bar.close, breakout_level)
    )
    reentry_count = sum(
        1 for bar in closed_bars if _reentered_structure(direction, bar, breakout_level)
    )
    reentry_fraction = reentry_count / len(closed_bars)

    consecutive_closes = 0
    acceptance_seconds = 0
    for bar in reversed(closed_bars):
        if not _beyond_level(direction, bar.close, breakout_level):
            break
        consecutive_closes += 1
        acceptance_seconds += bar.duration_seconds

    if not touched:
        state = BreakoutAcceptanceState.NOT_BROKEN
    elif beyond_count == 0 or reentry_fraction > policy.maximum_reentry_fraction:
        state = BreakoutAcceptanceState.REJECTED
    elif (
        consecutive_closes >= policy.minimum_consecutive_closes
        and acceptance_seconds >= policy.minimum_acceptance_seconds
    ):
        state = BreakoutAcceptanceState.ACCEPTED
    else:
        state = BreakoutAcceptanceState.PROVISIONAL

    return BreakoutAcceptanceAudit(
        direction=direction,
        breakout_level=breakout_level,
        state=state,
        consecutive_closes=consecutive_closes,
        acceptance_seconds=acceptance_seconds,
        reentry_fraction=reentry_fraction,
        evaluated_closed_bars=len(closed_bars),
    )


__all__ = [
    "BreakoutAcceptanceAudit",
    "BreakoutAcceptancePolicy",
    "BreakoutAcceptanceState",
    "BreakoutBarObservation",
    "audit_breakout_acceptance",
]
