"""Immutable contracts for deterministic Phase 8 backtesting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies import StrategyType, TradeDirection


class BacktestOutcome(StrEnum):
    TARGET = "target"
    STOP = "stop"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Execution assumptions used by deterministic trade simulation."""

    fee_pct: float = 0.04
    slippage_pct: float = 0.02
    maximum_holding_candles: int = 24
    conservative_intrabar: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("fee percentage", self.fee_pct),
            ("slippage percentage", self.slippage_pct),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.maximum_holding_candles < 1:
            raise ValueError("maximum holding candles must be positive")


@dataclass(frozen=True, slots=True)
class BacktestSignal:
    """Risk-approved setup reduced to execution fields required by a replay."""

    symbol: str
    strategy: StrategyType
    direction: TradeDirection
    generated_at: datetime
    entry_price: float
    stop_price: float
    target_price: float
    quantity: float
    risk_amount: float
    confidence_score: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("signal symbol cannot be empty")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("signal time must be timezone-aware")
        for name in (
            "entry_price",
            "stop_price",
            "target_price",
            "quantity",
            "risk_amount",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        if not math.isfinite(self.confidence_score) or not 0.0 <= self.confidence_score <= 100.0:
            raise ValueError("confidence score must be between zero and 100")
        if self.direction is TradeDirection.LONG:
            if not self.stop_price < self.entry_price < self.target_price:
                raise ValueError("long signal prices must be stop < entry < target")
        elif not self.target_price < self.entry_price < self.stop_price:
            raise ValueError("short signal prices must be target < entry < stop")


@dataclass(frozen=True, slots=True)
class SimulatedTrade:
    """One completed deterministic simulated trade."""

    signal: BacktestSignal
    outcome: BacktestOutcome
    exit_time: datetime
    exit_price: float
    gross_pnl: float
    fees: float
    net_pnl: float
    realized_r_multiple: float
    holding_candles: int

    def __post_init__(self) -> None:
        if self.exit_time.tzinfo is None or self.exit_time.utcoffset() is None:
            raise ValueError("exit time must be timezone-aware")
        if not math.isfinite(self.exit_price) or self.exit_price <= 0.0:
            raise ValueError("exit price must be positive and finite")
        for name in ("gross_pnl", "fees", "net_pnl", "realized_r_multiple"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.fees < 0.0:
            raise ValueError("fees cannot be negative")
        if self.holding_candles < 1:
            raise ValueError("holding candles must be positive")


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Aggregate deterministic backtest metrics."""

    trades: tuple[SimulatedTrade, ...]
    total_trades: int
    win_rate: float
    loss_rate: float
    breakeven_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float | None
    average_win: float
    average_loss: float
    average_risk_reward: float
    expectancy: float
    maximum_drawdown: float
    consecutive_wins: int
    consecutive_losses: int
    by_symbol: dict[str, int]
    by_strategy: dict[str, int]

    def __post_init__(self) -> None:
        if self.total_trades != len(self.trades):
            raise ValueError("total trades must match trade count")
        for name in ("win_rate", "loss_rate", "breakeven_rate"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in the unit interval")
