"""Immutable contracts for Phase 12 testnet-only execution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies import TradeDirection


class ExecutionState(StrEnum):
    PREVIEW = "preview"
    REJECTED = "rejected"
    TESTNET_SUBMITTED = "testnet_submitted"


class KillSwitchState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    enabled: bool = False
    testnet: bool = True
    max_order_notional: float = 500.0
    daily_loss_limit: float = 100.0

    def __post_init__(self) -> None:
        for name in ("max_order_notional", "daily_loss_limit"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        if not self.testnet:
            raise ValueError("execution config only supports testnet mode")


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    symbol: str
    direction: TradeDirection
    quantity: float
    entry_price: float
    stop_price: float
    target_price: float
    notional_value: float
    duplicate_key: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.duplicate_key.strip():
            raise ValueError("execution intent symbol and duplicate key cannot be empty")
        for name in ("quantity", "entry_price", "stop_price", "target_price", "notional_value"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")


@dataclass(frozen=True, slots=True)
class ExecutionOrder:
    order_id: str
    intent: ExecutionIntent
    state: ExecutionState
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("execution order identity cannot be empty")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("execution order time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: ExecutionState
    order: ExecutionOrder | None
    reasons: tuple[str, ...]
    audit_path: str | None = None

    def __post_init__(self) -> None:
        if self.state is ExecutionState.REJECTED:
            if self.order is not None or not self.reasons:
                raise ValueError("rejected execution requires reasons and no order")
        elif self.order is None:
            raise ValueError("non-rejected execution requires an order")
