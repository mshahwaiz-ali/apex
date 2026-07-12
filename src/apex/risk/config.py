"""Validated configuration for the deterministic Phase 6 risk engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class RiskProfile(StrEnum):
    CONTROLLED = "controlled"
    AGGRESSIVE = "aggressive"
    EXTREME = "extreme"


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")


@dataclass(frozen=True, slots=True)
class RiskConfig:
    identifier: str = "phase6-controlled-v1"
    profile: RiskProfile = RiskProfile.CONTROLLED
    account_equity: float = 10_000.0
    risk_per_trade_pct: float = 0.5
    minimum_risk_reward: float = 1.5
    minimum_stop_distance_pct: float = 0.15
    maximum_stop_distance_pct: float = 3.0
    structural_stop_buffer_pct: float = 0.05
    maximum_entry_chase_pct: float = 0.25
    maximum_leverage: float = 5.0
    maintenance_margin_pct: float = 0.5
    liquidation_buffer_ratio: float = 0.35
    maximum_concurrent_trades: int = 3
    maximum_open_risk_pct: float = 2.0
    maximum_directional_risk_pct: float = 1.5
    maximum_daily_loss_pct: float = 3.0
    maximum_consecutive_losses: int = 4

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("risk configuration identifier cannot be empty")
        for name in (
            "account_equity",
            "risk_per_trade_pct",
            "minimum_risk_reward",
            "minimum_stop_distance_pct",
            "maximum_stop_distance_pct",
            "structural_stop_buffer_pct",
            "maximum_entry_chase_pct",
            "maximum_leverage",
            "maintenance_margin_pct",
            "liquidation_buffer_ratio",
            "maximum_open_risk_pct",
            "maximum_directional_risk_pct",
            "maximum_daily_loss_pct",
        ):
            _positive(name.replace("_", " "), getattr(self, name))
        if self.minimum_stop_distance_pct >= self.maximum_stop_distance_pct:
            raise ValueError("minimum stop distance must be below maximum stop distance")
        if self.maximum_leverage < 1.0:
            raise ValueError("maximum leverage cannot be below one")
        if self.maximum_concurrent_trades < 1:
            raise ValueError("maximum concurrent trades must be positive")
        if self.maximum_consecutive_losses < 1:
            raise ValueError("maximum consecutive losses must be positive")
        if self.risk_per_trade_pct > self.maximum_open_risk_pct:
            raise ValueError("per-trade risk cannot exceed maximum open risk")
        if self.risk_per_trade_pct > self.maximum_directional_risk_pct:
            raise ValueError("per-trade risk cannot exceed maximum directional risk")


@dataclass(frozen=True, slots=True)
class ExposureState:
    open_trades: int = 0
    open_risk_amount: float = 0.0
    same_direction_risk_amount: float = 0.0
    daily_realized_loss: float = 0.0
    consecutive_losses: int = 0

    def __post_init__(self) -> None:
        if self.open_trades < 0 or self.consecutive_losses < 0:
            raise ValueError("exposure counters cannot be negative")
        for name in (
            "open_risk_amount",
            "same_direction_risk_amount",
            "daily_realized_loss",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        if self.same_direction_risk_amount > self.open_risk_amount:
            raise ValueError("same-direction risk cannot exceed total open risk")


DEFAULT_RISK_CONFIG = RiskConfig()
