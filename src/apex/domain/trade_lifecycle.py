"""Immutable contracts for deterministic futures trade lifecycle replay."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain import FuturesDirection


class TradeLifecycleState(StrEnum):
    PENDING_ENTRY = "PENDING_ENTRY"
    ENTRY_FILLED = "ENTRY_FILLED"
    TP1_HIT = "TP1_HIT"
    BREAKEVEN_ACTIVE = "BREAKEVEN_ACTIVE"
    TP2_HIT = "TP2_HIT"
    RUNNER_ACTIVE = "RUNNER_ACTIVE"
    TRAILING = "TRAILING"
    MOMENTUM_EXIT = "MOMENTUM_EXIT"
    TIME_EXIT = "TIME_EXIT"
    STOPPED = "STOPPED"
    INVALIDATED = "INVALIDATED"
    CLOSED = "CLOSED"


class TradeLifecycleEventType(StrEnum):
    ENTRY_FILLED = "entry_filled"
    TARGET_FILLED = "target_filled"
    STOP_MOVED = "stop_moved"
    TRAILING_ACTIVATED = "trailing_activated"
    POSITION_CLOSED = "position_closed"
    SETUP_INVALIDATED = "setup_invalidated"


@dataclass(frozen=True, slots=True)
class LifecycleTarget:
    label: str
    price: float
    close_percentage: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("lifecycle target label cannot be empty")
        _positive("lifecycle target price", self.price)
        _positive("lifecycle target close percentage", self.close_percentage)
        if self.close_percentage > 100.0:
            raise ValueError("lifecycle target close percentage cannot exceed 100")


@dataclass(frozen=True, slots=True)
class TradeLifecyclePlan:
    direction: FuturesDirection
    entry_zone_low: float
    entry_zone_high: float
    ideal_entry: float
    structural_stop: float
    targets: tuple[LifecycleTarget, ...]
    quantity: float
    fee_rate: float = 0.0
    slippage_rate: float = 0.0
    breakeven_offset_rate: float = 0.0
    maximum_pending_bars: int = 15
    maximum_open_bars: int = 60
    trailing_distance_rate: float = 0.005

    def __post_init__(self) -> None:
        for name, value in (
            ("entry zone low", self.entry_zone_low),
            ("entry zone high", self.entry_zone_high),
            ("ideal entry", self.ideal_entry),
            ("structural stop", self.structural_stop),
            ("quantity", self.quantity),
        ):
            _positive(name, value)
        if self.entry_zone_low > self.entry_zone_high:
            raise ValueError("entry zone low cannot exceed entry zone high")
        if not self.entry_zone_low <= self.ideal_entry <= self.entry_zone_high:
            raise ValueError("ideal entry must lie inside the entry zone")
        if not self.targets:
            raise ValueError("trade lifecycle requires at least one target")
        total = sum(target.close_percentage for target in self.targets)
        if not math.isclose(total, 100.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("lifecycle target close percentages must sum to 100")
        if self.direction is FuturesDirection.LONG:
            if self.structural_stop >= self.entry_zone_low:
                raise ValueError("long structural stop must be below the entry zone")
            if any(target.price <= self.entry_zone_high for target in self.targets):
                raise ValueError("long lifecycle targets must be above the entry zone")
        else:
            if self.structural_stop <= self.entry_zone_high:
                raise ValueError("short structural stop must be above the entry zone")
            if any(target.price >= self.entry_zone_low for target in self.targets):
                raise ValueError("short lifecycle targets must be below the entry zone")
        for name, value in (
            ("fee rate", self.fee_rate),
            ("slippage rate", self.slippage_rate),
            ("breakeven offset rate", self.breakeven_offset_rate),
            ("trailing distance rate", self.trailing_distance_rate),
        ):
            _nonnegative(name, value)
        if self.maximum_pending_bars <= 0 or self.maximum_open_bars <= 0:
            raise ValueError("lifecycle bar limits must be positive")


@dataclass(frozen=True, slots=True)
class TradeLifecycleObservation:
    observed_at: datetime
    high: float
    low: float
    close: float
    momentum_failed: bool = False
    fast_failure: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("lifecycle observation time must be timezone-aware")
        for name, value in (("high", self.high), ("low", self.low), ("close", self.close)):
            _positive(name, value)
        if self.low > self.high:
            raise ValueError("observation low cannot exceed high")
        if not self.low <= self.close <= self.high:
            raise ValueError("observation close must lie inside high-low range")


@dataclass(frozen=True, slots=True)
class TradeLifecycleEvent:
    event_type: TradeLifecycleEventType
    state: TradeLifecycleState
    observed_at: datetime
    price: float
    quantity_percentage: float
    reason: str


@dataclass(frozen=True, slots=True)
class TradeLifecycleResult:
    state: TradeLifecycleState
    entry_price: float | None
    active_stop: float
    remaining_quantity_percentage: float
    realized_pnl: float
    unrealized_pnl: float
    total_fees: float
    total_slippage: float
    realized_r_multiple: float
    bars_pending: int
    bars_open: int
    events: tuple[TradeLifecycleEvent, ...]
    exit_reason: str | None = None


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")


def _nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
