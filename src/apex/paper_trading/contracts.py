"""Immutable contracts for Phase 9 paper trading."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from apex.backtesting import BacktestSignal


class PaperTradeState(StrEnum):
    GENERATED = "generated"
    WAITING_FOR_ENTRY = "waiting_for_entry"
    ENTERED = "entered"
    PARTIALLY_CLOSED = "partially_closed"
    STOPPED = "stopped"
    TARGET_HIT = "target_hit"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


TERMINAL_STATES = frozenset(
    {
        PaperTradeState.STOPPED,
        PaperTradeState.TARGET_HIT,
        PaperTradeState.EXPIRED,
        PaperTradeState.CANCELLED,
        PaperTradeState.INVALIDATED,
    }
)


@dataclass(frozen=True, slots=True)
class PaperTradeConfig:
    """Paper-trade lifecycle assumptions."""

    entry_timeout_candles: int = 12
    maximum_holding_candles: int = 24
    fee_pct: float = 0.04
    slippage_pct: float = 0.02
    conservative_intrabar: bool = True

    def __post_init__(self) -> None:
        if self.entry_timeout_candles < 1:
            raise ValueError("entry timeout candles must be positive")
        if self.maximum_holding_candles < 1:
            raise ValueError("maximum holding candles must be positive")
        for name in ("fee_pct", "slippage_pct"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PaperTrade:
    """Auditable paper-trade lifecycle record."""

    trade_id: str
    signal: BacktestSignal
    state: PaperTradeState
    created_at: datetime
    updated_at: datetime
    analysis_payload: dict[str, Any]
    futures_plan: dict[str, Any] | None = None
    lifecycle_events: tuple[dict[str, Any], ...] = ()
    entry_time: datetime | None = None
    entry_price: float | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    net_pnl: float = 0.0
    realized_r_multiple: float = 0.0
    partial_target_count: int = 0
    closed_percentage: float = 0.0
    candles_waited: int = 0
    candles_held: int = 0
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("paper trade identity cannot be empty")
        for name in ("created_at", "updated_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name.replace('_', ' ')} must be timezone-aware")
        for name in ("entry_price", "exit_price"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        for name in ("net_pnl", "realized_r_multiple"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.partial_target_count < 0:
            raise ValueError("partial target count cannot be negative")
        if not math.isfinite(self.closed_percentage) or not 0.0 <= self.closed_percentage <= 100.0:
            raise ValueError("closed percentage must be between zero and 100")
        if self.candles_waited < 0 or self.candles_held < 0:
            raise ValueError("paper trade candle counters cannot be negative")
        if self.state in TERMINAL_STATES and self.exit_time is None:
            raise ValueError("terminal paper trades require an exit time")
        for event in self.lifecycle_events:
            if (
                not isinstance(event, dict)
                or "event_type" not in event
                or "occurred_at" not in event
            ):
                raise ValueError("paper lifecycle events require event_type and occurred_at")

    @property
    def is_open(self) -> bool:
        return self.state not in TERMINAL_STATES


@dataclass(frozen=True, slots=True)
class PaperPerformance:
    """Live paper-trading metrics from stored trades."""

    total_trades: int
    open_trades: int
    closed_trades: int
    net_pnl: float
    win_rate: float
    average_r_multiple: float
    by_state: dict[str, int]

    def __post_init__(self) -> None:
        if self.total_trades < 0 or self.open_trades < 0 or self.closed_trades < 0:
            raise ValueError("paper performance counts cannot be negative")
        if self.open_trades + self.closed_trades != self.total_trades:
            raise ValueError("open and closed counts must equal total trades")
        for name in ("net_pnl", "win_rate", "average_r_multiple"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if not 0.0 <= self.win_rate <= 1.0:
            raise ValueError("win rate must be in the unit interval")


@dataclass(frozen=True, slots=True)
class PaperReport:
    """Period-scoped paper-trading report."""

    period: str
    generated_at: datetime
    performance: PaperPerformance
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise ValueError("paper report period cannot be empty")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("paper report generation time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BacktestPaperComparison:
    """Compare paper outcomes to a reproducible backtest report."""

    generated_at: datetime
    backtest_total_trades: int
    paper_total_trades: int
    net_pnl_delta: float
    win_rate_delta: float
    average_r_delta: float
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("comparison generation time must be timezone-aware")
        if self.backtest_total_trades < 0 or self.paper_total_trades < 0:
            raise ValueError("comparison trade counts cannot be negative")
        for name in ("net_pnl_delta", "win_rate_delta", "average_r_delta"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
