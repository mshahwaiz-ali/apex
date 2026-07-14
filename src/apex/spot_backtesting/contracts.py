"""Typed contracts for deterministic long-only spot portfolio backtesting."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from collections.abc import Mapping
from types import MappingProxyType


class SpotMarketRegime(StrEnum):
    RISK_ON = "RISK_ON"
    SELECTIVE_RISK_ON = "SELECTIVE_RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    CAPITULATION = "CAPITULATION"
    RECOVERY = "RECOVERY"


class SpotExitReason(StrEnum):
    TARGET = "TARGET"
    STOP = "STOP"
    TIME = "TIME"
    REGIME = "REGIME"
    EXPIRY = "EXPIRY"
    FINAL_MARK = "FINAL_MARK"


@dataclass(frozen=True, slots=True)
class SpotBacktestConfig:
    starting_cash: float
    maximum_allocation_per_position_pct: float = 20.0
    maximum_total_exposure_pct: float = 80.0
    maximum_concurrent_positions: int = 5
    minimum_cash_reserve_pct: float = 10.0
    fee_pct: float = 0.10
    slippage_pct: float = 0.05
    allow_scale_in: bool = True
    maximum_scale_entries: int = 3
    maximum_holding: timedelta = timedelta(days=7)

    def __post_init__(self) -> None:
        if not math.isfinite(self.starting_cash) or self.starting_cash <= 0.0:
            raise ValueError("starting cash must be finite and positive")
        for name in (
            "maximum_allocation_per_position_pct",
            "maximum_total_exposure_pct",
            "minimum_cash_reserve_pct",
            "fee_pct",
            "slippage_pct",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        if self.maximum_allocation_per_position_pct > 100.0:
            raise ValueError("per-position allocation cannot exceed 100 percent")
        if self.maximum_total_exposure_pct > 100.0:
            raise ValueError("total exposure cannot exceed 100 percent")
        if self.minimum_cash_reserve_pct >= 100.0:
            raise ValueError("cash reserve must remain below 100 percent")
        if self.maximum_total_exposure_pct + self.minimum_cash_reserve_pct > 100.0:
            raise ValueError("exposure and reserve constraints conflict")
        if self.maximum_concurrent_positions < 1 or self.maximum_scale_entries < 1:
            raise ValueError("position and scale-entry limits must be positive")
        if self.maximum_holding <= timedelta(0):
            raise ValueError("maximum holding duration must be positive")


@dataclass(frozen=True, slots=True)
class SpotTarget:
    price: float
    fraction: float
    label: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.price) or self.price <= 0.0:
            raise ValueError("target price must be finite and positive")
        if not math.isfinite(self.fraction) or not 0.0 < self.fraction <= 1.0:
            raise ValueError("target fraction must be in (0, 1]")
        if not self.label.strip():
            raise ValueError("target label cannot be empty")


@dataclass(frozen=True, slots=True)
class SpotEntryLeg:
    price: float
    allocation_fraction: float
    trigger_at: datetime

    def __post_init__(self) -> None:
        if not math.isfinite(self.price) or self.price <= 0.0:
            raise ValueError("entry price must be finite and positive")
        if not math.isfinite(self.allocation_fraction) or not 0.0 < self.allocation_fraction <= 1.0:
            raise ValueError("allocation fraction must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class SpotOrderPlan:
    plan_id: str
    symbol: str
    strategy: str
    score_band: str
    market_regime: SpotMarketRegime
    created_at: datetime
    expires_at: datetime
    allocation_pct: float
    entries: tuple[SpotEntryLeg, ...]
    targets: tuple[SpotTarget, ...]
    protective_stop: float
    maximum_holding: timedelta | None = None
    exit_regimes: tuple[SpotMarketRegime, ...] = (
        SpotMarketRegime.RISK_OFF,
        SpotMarketRegime.CAPITULATION,
    )

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.symbol.strip() or not self.strategy.strip():
            raise ValueError("spot plan identity fields cannot be empty")
        if self.expires_at <= self.created_at:
            raise ValueError("spot plan expiry must follow creation")
        if not math.isfinite(self.allocation_pct) or not 0.0 < self.allocation_pct <= 100.0:
            raise ValueError("allocation percentage must be in (0, 100]")
        if not self.entries:
            raise ValueError("spot plan requires at least one entry")
        if sum(entry.allocation_fraction for entry in self.entries) > 1.0 + 1e-12:
            raise ValueError("entry allocation fractions cannot exceed one")
        if len({entry.trigger_at for entry in self.entries}) != len(self.entries):
            raise ValueError("entry triggers must be unique")
        if not self.targets:
            raise ValueError("spot plan requires at least one target")
        if sum(target.fraction for target in self.targets) > 1.0 + 1e-12:
            raise ValueError("target fractions cannot exceed one")
        if not math.isfinite(self.protective_stop) or self.protective_stop <= 0.0:
            raise ValueError("protective stop must be finite and positive")
        if any(entry.price <= self.protective_stop for entry in self.entries):
            raise ValueError("long-only spot entries must remain above the protective stop")
        if any(
            target.price <= min(entry.price for entry in self.entries) for target in self.targets
        ):
            raise ValueError("long-only spot targets must remain above planned entries")


@dataclass(frozen=True, slots=True)
class SpotBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    regime: SpotMarketRegime

    def __post_init__(self) -> None:
        values = (self.open, self.high, self.low, self.close)
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("spot bar prices must be finite and positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid spot OHLC geometry")


@dataclass(slots=True)
class SpotPosition:
    plan: SpotOrderPlan
    quantity: float = 0.0
    cost_basis: float = 0.0
    entry_fees: float = 0.0
    realized_pnl: float = 0.0
    filled_entry_indices: set[int] = field(default_factory=set)
    filled_target_indices: set[int] = field(default_factory=set)
    opened_at: datetime | None = None
    closed_at: datetime | None = None

    @property
    def average_entry(self) -> float:
        return self.cost_basis / self.quantity if self.quantity > 0.0 else 0.0


@dataclass(frozen=True, slots=True)
class SpotTradeRecord:
    plan_id: str
    symbol: str
    strategy: str
    score_band: str
    market_regime: str
    opened_at: datetime
    closed_at: datetime
    invested_cash: float
    proceeds: float
    net_pnl: float
    return_pct: float
    holding_duration_seconds: float
    exit_reason: SpotExitReason


@dataclass(frozen=True, slots=True)
class SpotEquityPoint:
    timestamp: datetime
    cash: float
    market_value: float
    equity: float
    exposure_pct: float
    concurrent_positions: int


@dataclass(frozen=True, slots=True)
class SpotPortfolioMetrics:
    trade_count: int
    win_rate: float
    average_return_pct: float
    expectancy_pct: float
    profit_factor: float | None
    maximum_drawdown_pct: float
    ending_equity: float
    total_return_pct: float
    average_exposure_pct: float
    maximum_exposure_pct: float
    average_concurrent_positions: float
    maximum_concurrent_positions: int
    average_holding_duration_seconds: float
    strategy_breakdown: Mapping[str, float]
    symbol_breakdown: Mapping[str, float]
    regime_breakdown: Mapping[str, float]
    score_band_breakdown: Mapping[str, float]
    exit_reason_breakdown: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "strategy_breakdown",
            "symbol_breakdown",
            "regime_breakdown",
            "score_band_breakdown",
            "exit_reason_breakdown",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


@dataclass(frozen=True, slots=True)
class SpotBacktestResult:
    config: SpotBacktestConfig
    starting_cash: float
    current_cash: float
    portfolio_equity: float
    trades: tuple[SpotTradeRecord, ...]
    equity_curve: tuple[SpotEquityPoint, ...]
    metrics: SpotPortfolioMetrics
    warnings: tuple[str, ...] = (
        "historical spot results do not guarantee future returns",
        "forward-paper validation remains required",
    )
