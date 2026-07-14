"""Canonical manual trade-management contracts for futures plans.

These provider-independent models validate direction-aware geometry,
allocation arithmetic, and action consistency before instructions are shown to
an operator or serialized into an analysis record.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.futures import EntryState, FuturesDirection
from apex.domain.lifecycle import TradeLifecycleEvent, TradeLifecycleEventType


class CurrentAction(StrEnum):
    HOLD = "HOLD"
    ENTER = "ENTER"
    DO_NOT_ENTER = "DO_NOT_ENTER"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    MOVE_STOP = "MOVE_STOP"
    CLOSE_ALL = "CLOSE_ALL"
    CANCEL_SETUP = "CANCEL_SETUP"
    WAIT = "WAIT"


class EntryInstructionAction(StrEnum):
    ENTER_NOW = "ENTER_NOW"
    PLACE_LIMIT = "PLACE_LIMIT"
    WAIT_FOR_RETEST = "WAIT_FOR_RETEST"
    WAIT_FOR_RECLAIM = "WAIT_FOR_RECLAIM"
    WATCH = "WATCH"
    REJECT = "REJECT"


class RecommendedOrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LIMIT = "STOP_LIMIT"
    NONE = "NONE"


class StopInstructionType(StrEnum):
    HARD_STOP = "HARD_STOP"
    STOP_MARKET = "STOP_MARKET"


class ManagementTriggerType(StrEnum):
    TARGET_FILLED = "TARGET_FILLED"
    PRICE_REACHED = "PRICE_REACHED"
    CANDLE_CLOSE = "CANDLE_CLOSE"
    STRUCTURAL_BREAK = "STRUCTURAL_BREAK"
    SPREAD_EXPANSION = "SPREAD_EXPANSION"
    ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT"


class EntryInstruction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: EntryInstructionAction
    entry_state: EntryState
    zone_low: float = Field(gt=0)
    zone_high: float = Field(gt=0)
    ideal_entry: float = Field(gt=0)
    maximum_chase_price: float = Field(gt=0)
    order_type: RecommendedOrderType
    expires_at: datetime | None = None
    cancellation_conditions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_instruction(self) -> Self:
        if self.zone_low > self.zone_high:
            raise ValueError("entry zone low cannot exceed entry zone high")
        if not self.zone_low <= self.ideal_entry <= self.zone_high:
            raise ValueError("ideal entry must remain inside the entry zone")
        if self.expires_at is not None and (
            self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None
        ):
            raise ValueError("entry expiry must be timezone-aware")
        if self.action is EntryInstructionAction.REJECT:
            if self.order_type is not RecommendedOrderType.NONE:
                raise ValueError("rejected entries cannot recommend an order type")
        elif self.order_type is RecommendedOrderType.NONE:
            raise ValueError("actionable entry instructions require an order type")
        return self


class InitialProtectionInstruction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stop_loss_price: float = Field(gt=0)
    stop_type: StopInstructionType
    risk_percentage: float = Field(gt=0, le=100)
    risk_amount: float = Field(gt=0)
    quantity: float = Field(gt=0)
    notional: float = Field(gt=0)
    margin: float = Field(gt=0)
    leverage: float = Field(gt=0)
    estimated_fees: float = Field(ge=0)
    estimated_slippage: float = Field(ge=0)
    estimated_liquidation_price: float = Field(gt=0)
    stop_to_liquidation_buffer: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_margin(self) -> Self:
        expected_margin = self.notional / self.leverage
        if abs(self.margin - expected_margin) > max(1e-8, expected_margin * 1e-8):
            raise ValueError("margin must equal notional divided by leverage")
        return self


class ManagementTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    price: float = Field(gt=0)
    close_percentage: float = Field(gt=0, le=100)
    cumulative_close_percentage: float = Field(gt=0, le=100)
    expected_r_multiple: float
    rationale: str = Field(min_length=1)


class StopManagementRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger_type: ManagementTriggerType
    trigger_reference: str = Field(min_length=1)
    action: CurrentAction
    stop_price: float | None = Field(default=None, gt=0)
    instruction: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_stop_action(self) -> Self:
        if self.action is CurrentAction.MOVE_STOP and self.stop_price is None:
            raise ValueError("MOVE_STOP rules require stop_price")
        if self.action is not CurrentAction.MOVE_STOP and self.stop_price is not None:
            raise ValueError("only MOVE_STOP rules may define stop_price")
        return self


class EmergencyExitRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger_type: ManagementTriggerType
    condition: str = Field(min_length=1)
    action: CurrentAction = CurrentAction.CLOSE_ALL

    @model_validator(mode="after")
    def validate_terminal_action(self) -> Self:
        if self.action not in {
            CurrentAction.CLOSE_ALL,
            CurrentAction.CANCEL_SETUP,
        }:
            raise ValueError("emergency rules must close the trade or cancel the setup")
        return self


class TradeManagementPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: FuturesDirection
    entry: EntryInstruction
    initial_protection: InitialProtectionInstruction
    targets: tuple[ManagementTarget, ...] = Field(min_length=1)
    stop_management: tuple[StopManagementRule, ...] = ()
    emergency_exits: tuple[EmergencyExitRule, ...] = Field(min_length=1)
    current_action: CurrentAction

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        total = sum(target.close_percentage for target in self.targets)
        if abs(total - 100.0) > 1e-9:
            raise ValueError("management target percentages must total 100")
        cumulative = 0.0
        labels: set[str] = set()
        previous_price: float | None = None
        for target in self.targets:
            if target.label in labels:
                raise ValueError("management target labels must be unique")
            labels.add(target.label)
            cumulative += target.close_percentage
            if abs(target.cumulative_close_percentage - cumulative) > 1e-9:
                raise ValueError("target cumulative close percentage is inconsistent")
            if previous_price is not None:
                if (
                    self.direction is FuturesDirection.LONG
                    and target.price <= previous_price
                ):
                    raise ValueError("long targets must increase in price")
                if (
                    self.direction is FuturesDirection.SHORT
                    and target.price >= previous_price
                ):
                    raise ValueError("short targets must decrease in price")
            previous_price = target.price
        if self.current_action is CurrentAction.ENTER and self.entry.action not in {
            EntryInstructionAction.ENTER_NOW,
            EntryInstructionAction.PLACE_LIMIT,
        }:
            raise ValueError("ENTER requires an immediately actionable entry instruction")
        if (
            self.current_action is CurrentAction.DO_NOT_ENTER
            and self.entry.action is not EntryInstructionAction.REJECT
        ):
            raise ValueError("DO_NOT_ENTER requires a rejected entry instruction")
        return self


def entry_action_for_state(
    state: EntryState,
) -> tuple[EntryInstructionAction, CurrentAction]:
    """Map one canonical entry state to one non-contradictory operator action."""

    mapping = {
        EntryState.READY_NOW: (
            EntryInstructionAction.ENTER_NOW,
            CurrentAction.ENTER,
        ),
        EntryState.WAIT_FOR_RETEST: (
            EntryInstructionAction.WAIT_FOR_RETEST,
            CurrentAction.WAIT,
        ),
        EntryState.WAIT_FOR_RECLAIM: (
            EntryInstructionAction.WAIT_FOR_RECLAIM,
            CurrentAction.WAIT,
        ),
        EntryState.APPROACHING_ENTRY: (
            EntryInstructionAction.PLACE_LIMIT,
            CurrentAction.WAIT,
        ),
        EntryState.WATCH: (
            EntryInstructionAction.WATCH,
            CurrentAction.WAIT,
        ),
        EntryState.MISSED_ENTRY: (
            EntryInstructionAction.REJECT,
            CurrentAction.DO_NOT_ENTER,
        ),
        EntryState.INVALIDATED: (
            EntryInstructionAction.REJECT,
            CurrentAction.DO_NOT_ENTER,
        ),
        EntryState.NO_TRADE: (
            EntryInstructionAction.REJECT,
            CurrentAction.DO_NOT_ENTER,
        ),
    }
    return mapping[state]


def lifecycle_event_for_action(
    action: CurrentAction,
    *,
    occurred_at: datetime,
    stop_price: float | None = None,
    target_label: str | None = None,
    closed_percentage: float | None = None,
    reason: str | None = None,
) -> TradeLifecycleEvent | None:
    """Translate supported management actions into canonical lifecycle events.

    HOLD and WAIT are intentionally state-preserving and therefore emit no
    lifecycle event.
    """

    if action in {CurrentAction.HOLD, CurrentAction.WAIT}:
        return None
    event_types = {
        CurrentAction.ENTER: TradeLifecycleEventType.ENTRY_FILLED,
        CurrentAction.DO_NOT_ENTER: TradeLifecycleEventType.CANCELLED,
        CurrentAction.PARTIAL_CLOSE: TradeLifecycleEventType.PARTIAL_TARGET_HIT,
        CurrentAction.MOVE_STOP: TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN,
        CurrentAction.CLOSE_ALL: TradeLifecycleEventType.EMERGENCY_STOP,
        CurrentAction.CANCEL_SETUP: TradeLifecycleEventType.CANCELLED,
    }
    return TradeLifecycleEvent(
        event_type=event_types[action],
        occurred_at=occurred_at,
        stop_price=stop_price,
        target_label=target_label,
        closed_percentage=closed_percentage,
        reason=reason or action.value,
    )
