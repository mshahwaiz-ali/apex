"""Provider-independent spot trading contracts.

Spot is intentionally separate from perpetual-futures contracts. These models do
not contain leverage, margin, liquidation, maintenance-margin, or borrowed-asset
semantics.
"""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpotDirection(StrEnum):
    LONG = "LONG"


class SpotOrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SpotDecision(StrEnum):
    BUY = "BUY"
    WATCH = "WATCH"
    HOLD_EXISTING = "HOLD_EXISTING"
    REDUCE = "REDUCE"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class SpotMarketRegime(StrEnum):
    RISK_ON = "RISK_ON"
    SELECTIVE_RISK_ON = "SELECTIVE_RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    CAPITULATION = "CAPITULATION"
    RECOVERY = "RECOVERY"


class SpotEntryState(StrEnum):
    WATCH = "WATCH"
    APPROACHING_ENTRY = "APPROACHING_ENTRY"
    READY_NOW = "READY_NOW"
    WAIT_FOR_RECLAIM = "WAIT_FOR_RECLAIM"
    WAIT_FOR_RETEST = "WAIT_FOR_RETEST"
    MISSED_ENTRY = "MISSED_ENTRY"
    INVALIDATED = "INVALIDATED"
    NO_TRADE = "NO_TRADE"


class SpotLifecycleState(StrEnum):
    GENERATED = "GENERATED"
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PARTIALLY_REDUCED = "PARTIALLY_REDUCED"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"


class SpotBalanceInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset: str = Field(min_length=1)
    available: float = Field(ge=0)
    reserved: float = Field(default=0.0, ge=0)

    @property
    def total(self) -> float:
        return self.available + self.reserved


class SpotAccountInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quote_asset: str = Field(min_length=1)
    available_quote_balance: float = Field(ge=0)
    total_spot_equity: float = Field(gt=0)
    current_spot_exposure: float = Field(default=0.0, ge=0)
    open_position_count: int = Field(default=0, ge=0)
    balances: tuple[SpotBalanceInput, ...] = ()

    @model_validator(mode="after")
    def validate_account_geometry(self) -> Self:
        if self.available_quote_balance > self.total_spot_equity:
            raise ValueError("available quote balance cannot exceed total spot equity")
        if self.current_spot_exposure > self.total_spot_equity:
            raise ValueError("current spot exposure cannot exceed total spot equity")
        assets = [balance.asset.upper() for balance in self.balances]
        if len(assets) != len(set(assets)):
            raise ValueError("spot balance assets must be unique")
        return self


class SpotEntryLeg(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    price: float = Field(gt=0)
    allocation_percentage: float = Field(gt=0, le=100)
    requires_confirmation: bool = False


class SpotEntryPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: SpotDirection = SpotDirection.LONG
    side: SpotOrderSide = SpotOrderSide.BUY
    state: SpotEntryState
    current_price: float = Field(gt=0)
    entries: tuple[SpotEntryLeg, ...] = Field(min_length=1, max_length=3)
    maximum_chase_price: float = Field(gt=0)
    invalidation_price: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_entry_plan(self) -> Self:
        if self.direction is not SpotDirection.LONG or self.side is not SpotOrderSide.BUY:
            raise ValueError("initial Apex spot entries are long-only BUY plans")
        total = sum(entry.allocation_percentage for entry in self.entries)
        if abs(total - 100.0) > 1e-9:
            raise ValueError("spot entry allocation percentages must total 100")
        labels = [entry.label for entry in self.entries]
        if len(labels) != len(set(labels)):
            raise ValueError("spot entry labels must be unique")
        prices = [entry.price for entry in self.entries]
        if any(later > earlier for earlier, later in pairwise(prices)):
            raise ValueError("spot scale-in entry prices must be non-increasing")
        if self.maximum_chase_price < prices[0]:
            raise ValueError("spot maximum chase price cannot be below the first entry")
        if self.invalidation_price >= min(prices):
            raise ValueError("spot invalidation must be below every planned entry")
        if self.state is SpotEntryState.READY_NOW and self.current_price > self.maximum_chase_price:
            raise ValueError("READY_NOW cannot be beyond the maximum chase price")
        if self.state is SpotEntryState.MISSED_ENTRY and self.current_price <= self.maximum_chase_price:
            raise ValueError("MISSED_ENTRY requires price beyond maximum chase")
        return self


class SpotStopPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    structural_invalidation_price: float = Field(gt=0)
    protective_stop_price: float = Field(gt=0)
    thesis_failure_reason: str = Field(min_length=1)
    market_regime_exit_required: bool = True

    @model_validator(mode="after")
    def validate_stop_geometry(self) -> Self:
        if self.protective_stop_price > self.structural_invalidation_price:
            raise ValueError("spot protective stop cannot exceed structural invalidation")
        return self


class SpotTargetLeg(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    price: float = Field(gt=0)
    sell_percentage: float = Field(gt=0, le=100)
    rationale: str = Field(min_length=1)


class SpotTargetPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: tuple[SpotTargetLeg, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        total = sum(target.sell_percentage for target in self.targets)
        if abs(total - 100.0) > 1e-9:
            raise ValueError("spot target sell percentages must total 100")
        prices = [target.price for target in self.targets]
        if any(later <= earlier for earlier, later in pairwise(prices)):
            raise ValueError("spot target prices must be strictly increasing")
        labels = [target.label for target in self.targets]
        if len(labels) != len(set(labels)):
            raise ValueError("spot target labels must be unique")
        return self


class SpotPositionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    average_entry_price: float = Field(gt=0)
    quantity: float = Field(gt=0)
    capital_allocated: float = Field(gt=0)
    allocation_percentage_of_equity: float = Field(gt=0, le=100)
    planned_loss_amount: float = Field(gt=0)
    planned_loss_percentage_of_equity: float = Field(gt=0, le=100)
    remaining_quote_reserve: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_position_arithmetic(self) -> Self:
        expected = self.average_entry_price * self.quantity
        tolerance = max(1e-8, expected * 1e-8)
        if abs(self.capital_allocated - expected) > tolerance:
            raise ValueError("spot capital allocated must equal average entry price times quantity")
        if self.planned_loss_amount >= self.capital_allocated:
            raise ValueError("spot planned loss must be below allocated capital")
        return self


class SpotLifecycleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: SpotLifecycleState
    filled_entry_labels: tuple[str, ...] = ()
    completed_target_labels: tuple[str, ...] = ()
    open_quantity: float = Field(default=0.0, ge=0)
    active_stop_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_lifecycle_snapshot(self) -> Self:
        if len(self.filled_entry_labels) != len(set(self.filled_entry_labels)):
            raise ValueError("filled spot entry labels must be unique")
        if len(self.completed_target_labels) != len(set(self.completed_target_labels)):
            raise ValueError("completed spot target labels must be unique")
        terminal = {
            SpotLifecycleState.CLOSED,
            SpotLifecycleState.STOPPED,
            SpotLifecycleState.EXPIRED,
            SpotLifecycleState.CANCELLED,
            SpotLifecycleState.INVALIDATED,
        }
        if self.state in terminal and self.open_quantity != 0:
            raise ValueError("terminal spot lifecycle states cannot retain open quantity")
        if (
            self.state in {SpotLifecycleState.FILLED, SpotLifecycleState.PARTIALLY_REDUCED}
            and self.open_quantity <= 0
        ):
            raise ValueError("active spot lifecycle states require open quantity")
        return self
