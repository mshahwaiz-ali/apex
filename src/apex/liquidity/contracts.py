"""Immutable contracts for liquidity, sweep, and trap analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.structure.contracts import BreakDirection, ConfirmationStatus


class LiquiditySide(StrEnum):
    BUY_SIDE = "buy_side"
    SELL_SIDE = "sell_side"


class LiquidityZoneType(StrEnum):
    EQUAL_HIGHS = "equal_highs"
    EQUAL_LOWS = "equal_lows"
    CLUSTERED_HIGHS = "clustered_highs"
    CLUSTERED_LOWS = "clustered_lows"
    PIVOT_HIGH = "pivot_high"
    PIVOT_LOW = "pivot_low"
    RANGE_HIGH = "range_high"
    RANGE_LOW = "range_low"


class LiquidityZoneStatus(StrEnum):
    ACTIVE = "active"
    BREACHED = "breached"
    SWEPT = "swept"
    CONSUMED = "consumed"


class SweepClassification(StrEnum):
    CONFIRMED_SWEEP = "confirmed_sweep"
    DEVELOPING_SWEEP = "developing_sweep"
    SIMPLE_BREAKOUT = "simple_breakout"
    UNRESOLVED_BREACH = "unresolved_breach"


class TrapType(StrEnum):
    BULL_TRAP = "bull_trap"
    BEAR_TRAP = "bear_trap"
    FAILED_BREAKOUT = "failed_breakout"
    BREAKOUT_REJECTION = "breakout_rejection"
    LATE_CHASE_RISK = "late_chase_risk"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class LiquidityZone:
    side: LiquiditySide
    kind: LiquidityZoneType
    low: float
    high: float
    representative_price: float
    source_pivot_indices: tuple[int, ...]
    touch_count: int
    created_index: int
    last_touch_index: int
    age: int
    status: LiquidityZoneStatus
    strength: float

    def __post_init__(self) -> None:
        for name, value in (
            ("zone low", self.low),
            ("zone high", self.high),
            ("representative price", self.representative_price),
        ):
            _finite(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.low > self.high:
            raise ValueError("zone low cannot exceed zone high")
        if not self.low <= self.representative_price <= self.high:
            raise ValueError("representative price must lie inside the zone")
        if self.touch_count < 1 or self.touch_count != len(self.source_pivot_indices):
            raise ValueError("touch count must match source pivots")
        if self.created_index < 0 or self.last_touch_index < self.created_index or self.age < 0:
            raise ValueError("invalid liquidity-zone indices")
        _finite("zone strength", self.strength)
        if not 0 <= self.strength <= 1:
            raise ValueError("zone strength must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LiquiditySweep:
    zone: LiquidityZone
    direction: BreakDirection
    candle_index: int
    candle_time: datetime
    penetration: float
    close_recovery: float
    classification: SweepClassification
    confirmation: ConfirmationStatus
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.candle_index < 0:
            raise ValueError("sweep candle index cannot be negative")
        _finite("sweep penetration", self.penetration)
        _finite("close recovery", self.close_recovery)
        if self.penetration < 0:
            raise ValueError("sweep penetration cannot be negative")


@dataclass(frozen=True, slots=True)
class TrapEvent:
    kind: TrapType
    candle_index: int
    candle_time: datetime
    zone: LiquidityZone
    sweep: LiquiditySweep | None
    confirmation: ConfirmationStatus
    evidence: tuple[str, ...]
    invalidation: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.candle_index < 0:
            raise ValueError("trap candle index cannot be negative")
