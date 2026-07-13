"""Provider-independent futures trading contracts.

These models freeze the first futures-only product contract without changing
strategy behavior. They are intentionally exchange-agnostic and can be used by
CLI, risk, backtesting, paper-trading, and later testnet execution layers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarginMode(StrEnum):
    ISOLATED = "ISOLATED"


class LeverageMode(StrEnum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"


class RiskMode(StrEnum):
    STANDARD = "STANDARD"
    AGGRESSIVE = "AGGRESSIVE"
    EXTREME = "EXTREME"


class FuturesDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class EntryState(StrEnum):
    WATCH = "WATCH"
    APPROACHING_ENTRY = "APPROACHING_ENTRY"
    READY_NOW = "READY_NOW"
    WAIT_FOR_RECLAIM = "WAIT_FOR_RECLAIM"
    WAIT_FOR_RETEST = "WAIT_FOR_RETEST"
    MISSED_ENTRY = "MISSED_ENTRY"
    INVALIDATED = "INVALIDATED"
    NO_TRADE = "NO_TRADE"


class TradeLifecycleState(StrEnum):
    GENERATED = "GENERATED"
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    ENTERED = "ENTERED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    STOPPED = "STOPPED"
    TARGET_HIT = "TARGET_HIT"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"


class FuturesAccountInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    wallet_balance: float = Field(gt=0)
    leverage_mode: LeverageMode = LeverageMode.AUTOMATIC
    manual_leverage: float | None = Field(default=None, gt=0)
    risk_mode: RiskMode = RiskMode.AGGRESSIVE
    maximum_account_loss_percentage: float = Field(gt=0, le=100)
    margin_mode: MarginMode = MarginMode.ISOLATED

    @model_validator(mode="after")
    def validate_leverage_selection(self) -> Self:
        if self.margin_mode is not MarginMode.ISOLATED:
            raise ValueError("Apex futures positions must use isolated margin")
        if self.leverage_mode is LeverageMode.MANUAL and self.manual_leverage is None:
            raise ValueError("manual leverage is required when leverage mode is MANUAL")
        if self.leverage_mode is LeverageMode.AUTOMATIC and self.manual_leverage is not None:
            raise ValueError("manual leverage must be omitted when leverage mode is AUTOMATIC")
        return self

    @property
    def maximum_account_loss_amount(self) -> float:
        return self.wallet_balance * (self.maximum_account_loss_percentage / 100)


class EntryPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: FuturesDirection = FuturesDirection.LONG
    state: EntryState
    current_price: float = Field(gt=0)
    zone_low: float = Field(gt=0)
    zone_high: float = Field(gt=0)
    ideal_entry: float = Field(gt=0)
    maximum_chase_price: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if self.zone_low > self.zone_high:
            raise ValueError("entry zone low cannot exceed entry zone high")
        if not self.zone_low <= self.ideal_entry <= self.zone_high:
            raise ValueError("ideal entry must remain inside the entry zone")
        if self.direction is FuturesDirection.LONG:
            if self.maximum_chase_price < self.zone_high:
                raise ValueError("long maximum chase price cannot be below the entry-zone high")
            missed = self.current_price > self.maximum_chase_price
        else:
            if self.maximum_chase_price > self.zone_low:
                raise ValueError("short maximum chase price cannot be above the entry-zone low")
            missed = self.current_price < self.maximum_chase_price
        if self.state is EntryState.READY_NOW and not self.zone_low <= self.current_price <= self.zone_high:
            raise ValueError("READY_NOW requires current price inside the entry zone")
        if self.state is EntryState.MISSED_ENTRY and not missed:
            raise ValueError("MISSED_ENTRY requires current price beyond maximum chase")
        return self


class StopPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    soft_failure: float = Field(gt=0)
    structural_stop: float = Field(gt=0)
    emergency_stop: float = Field(gt=0)
    rationale: str = Field(min_length=1)


class TargetLeg(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    price: float = Field(gt=0)
    close_percentage: float = Field(gt=0, le=100)


class TargetPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: tuple[TargetLeg, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_total_allocation(self) -> Self:
        total = sum(target.close_percentage for target in self.targets)
        if abs(total - 100.0) > 1e-9:
            raise ValueError("target close percentages must total 100")
        labels = [target.label for target in self.targets]
        if len(labels) != len(set(labels)):
            raise ValueError("target labels must be unique")
        return self


class PositionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    leverage: float = Field(gt=0)
    position_notional: float = Field(gt=0)
    required_margin: float = Field(gt=0)
    wallet_exposure_percentage: float = Field(gt=0, le=100)
    planned_loss_amount: float = Field(gt=0)
    estimated_fees: float = Field(ge=0)
    estimated_slippage: float = Field(ge=0)
    liquidation_price: float = Field(gt=0)
    margin_mode: MarginMode = MarginMode.ISOLATED

    @model_validator(mode="after")
    def validate_position_arithmetic(self) -> Self:
        expected_margin = self.position_notional / self.leverage
        tolerance = max(1e-8, expected_margin * 1e-8)
        if abs(self.required_margin - expected_margin) > tolerance:
            raise ValueError("required margin must equal position notional divided by leverage")
        if self.margin_mode is not MarginMode.ISOLATED:
            raise ValueError("Apex position plans must use isolated margin")
        return self
