"""Validated lifecycle state machine for futures trade plans."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.futures import TradeLifecycleState


class TradeLifecycleEventType(StrEnum):
    SETUP_GENERATED = "SETUP_GENERATED"
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    ENTRY_FILLED = "ENTRY_FILLED"
    PARTIAL_TARGET_HIT = "PARTIAL_TARGET_HIT"
    STOP_MOVED_TO_BREAKEVEN = "STOP_MOVED_TO_BREAKEVEN"
    RUNNER_ACTIVATED = "RUNNER_ACTIVATED"
    TRAILING_STOP_UPDATED = "TRAILING_STOP_UPDATED"
    MOMENTUM_FAILURE_EXIT = "MOMENTUM_FAILURE_EXIT"
    TIME_EXIT = "TIME_EXIT"
    STRUCTURAL_INVALIDATION = "STRUCTURAL_INVALIDATION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    FULL_TARGET_HIT = "FULL_TARGET_HIT"
    STOPPED_OUT = "STOPPED_OUT"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TERMINAL_LIFECYCLE_STATES = frozenset(
    {
        TradeLifecycleState.STOPPED,
        TradeLifecycleState.TARGET_HIT,
        TradeLifecycleState.EXPIRED,
        TradeLifecycleState.CANCELLED,
        TradeLifecycleState.INVALIDATED,
    }
)

ALLOWED_LIFECYCLE_TRANSITIONS: dict[TradeLifecycleState, frozenset[TradeLifecycleState]] = {
    TradeLifecycleState.GENERATED: frozenset(
        {
            TradeLifecycleState.WAITING_FOR_ENTRY,
            TradeLifecycleState.ENTERED,
            TradeLifecycleState.EXPIRED,
            TradeLifecycleState.CANCELLED,
            TradeLifecycleState.INVALIDATED,
        }
    ),
    TradeLifecycleState.WAITING_FOR_ENTRY: frozenset(
        {
            TradeLifecycleState.ENTERED,
            TradeLifecycleState.EXPIRED,
            TradeLifecycleState.CANCELLED,
            TradeLifecycleState.INVALIDATED,
        }
    ),
    TradeLifecycleState.ENTERED: frozenset(
        {
            TradeLifecycleState.PARTIALLY_CLOSED,
            TradeLifecycleState.STOPPED,
            TradeLifecycleState.TARGET_HIT,
            TradeLifecycleState.CANCELLED,
            TradeLifecycleState.INVALIDATED,
        }
    ),
    TradeLifecycleState.PARTIALLY_CLOSED: frozenset(
        {
            TradeLifecycleState.PARTIALLY_CLOSED,
            TradeLifecycleState.STOPPED,
            TradeLifecycleState.TARGET_HIT,
            TradeLifecycleState.CANCELLED,
            TradeLifecycleState.INVALIDATED,
        }
    ),
    TradeLifecycleState.STOPPED: frozenset(),
    TradeLifecycleState.TARGET_HIT: frozenset(),
    TradeLifecycleState.EXPIRED: frozenset(),
    TradeLifecycleState.CANCELLED: frozenset(),
    TradeLifecycleState.INVALIDATED: frozenset(),
}


class TradeLifecycle(BaseModel):
    """Immutable lifecycle snapshot shared by analysis and future execution layers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: TradeLifecycleState = TradeLifecycleState.GENERATED
    created_at: datetime
    updated_at: datetime
    entered_at: datetime | None = None
    closed_at: datetime | None = None
    closed_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    active_stop_price: float | None = Field(default=None, gt=0)
    trailing_stop_price: float | None = Field(default=None, gt=0)
    runner_active: bool = False
    partial_targets_hit: tuple[str, ...] = ()
    last_target_label: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> TradeLifecycle:
        for name, value in (("created_at", self.created_at), ("updated_at", self.updated_at)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.entered_at is not None:
            if self.entered_at.tzinfo is None or self.entered_at.utcoffset() is None:
                raise ValueError("entered_at must be timezone-aware")
            if self.entered_at < self.created_at or self.entered_at > self.updated_at:
                raise ValueError("entered_at must fall inside the lifecycle window")
        if self.closed_at is not None:
            if self.closed_at.tzinfo is None or self.closed_at.utcoffset() is None:
                raise ValueError("closed_at must be timezone-aware")
            if self.closed_at < self.created_at or self.closed_at > self.updated_at:
                raise ValueError("closed_at must fall inside the lifecycle window")
        if (
            self.state
            in {
                TradeLifecycleState.ENTERED,
                TradeLifecycleState.PARTIALLY_CLOSED,
                TradeLifecycleState.STOPPED,
                TradeLifecycleState.TARGET_HIT,
            }
            and self.entered_at is None
        ):
            raise ValueError(f"{self.state.value} requires entered_at")
        if (
            self.state is TradeLifecycleState.PARTIALLY_CLOSED
            and not 0 < self.closed_percentage < 100
        ):
            raise ValueError("PARTIALLY_CLOSED requires closed_percentage between zero and 100")
        if self.state is TradeLifecycleState.TARGET_HIT and self.closed_percentage != 100:
            raise ValueError("TARGET_HIT requires closed_percentage equal to 100")
        if self.state in TERMINAL_LIFECYCLE_STATES and self.closed_at is None:
            raise ValueError(f"{self.state.value} requires closed_at")
        if self.state not in TERMINAL_LIFECYCLE_STATES and self.closed_at is not None:
            raise ValueError("non-terminal lifecycle state cannot have closed_at")
        if self.trailing_stop_price is not None and not self.runner_active:
            raise ValueError("trailing stop requires an active runner")
        if self.runner_active and self.entered_at is None:
            raise ValueError("active runner requires entered_at")
        if len(set(self.partial_targets_hit)) != len(self.partial_targets_hit):
            raise ValueError("partial target labels must be unique")
        if self.partial_targets_hit and self.closed_percentage <= 0:
            raise ValueError("partial target labels require closed percentage")
        return self

    def transition(
        self,
        state: TradeLifecycleState,
        *,
        at: datetime,
        closed_percentage: float | None = None,
        active_stop_price: float | None = None,
        trailing_stop_price: float | None = None,
        runner_active: bool | None = None,
        target_label: str | None = None,
        reason: str | None = None,
    ) -> TradeLifecycle:
        """Return the next validated lifecycle snapshot."""

        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("transition time must be timezone-aware")
        if at < self.updated_at:
            raise ValueError("transition time cannot precede the current lifecycle timestamp")
        if state not in ALLOWED_LIFECYCLE_TRANSITIONS[self.state]:
            raise ValueError(f"invalid lifecycle transition: {self.state.value} -> {state.value}")

        entered_at = self.entered_at
        if state is TradeLifecycleState.ENTERED and entered_at is None:
            entered_at = at

        next_closed_percentage = (
            self.closed_percentage if closed_percentage is None else closed_percentage
        )
        if next_closed_percentage < self.closed_percentage:
            raise ValueError("closed percentage cannot decrease")
        if state is TradeLifecycleState.TARGET_HIT:
            next_closed_percentage = 100.0

        partial_targets_hit = self.partial_targets_hit
        if target_label is not None and state is TradeLifecycleState.PARTIALLY_CLOSED:
            partial_targets_hit = (*partial_targets_hit, target_label)

        closed_at = at if state in TERMINAL_LIFECYCLE_STATES else None
        return TradeLifecycle(
            state=state,
            created_at=self.created_at,
            updated_at=at,
            entered_at=entered_at,
            closed_at=closed_at,
            closed_percentage=next_closed_percentage,
            active_stop_price=active_stop_price
            if active_stop_price is not None
            else self.active_stop_price,
            trailing_stop_price=trailing_stop_price
            if trailing_stop_price is not None
            else self.trailing_stop_price,
            runner_active=self.runner_active if runner_active is None else runner_active,
            partial_targets_hit=partial_targets_hit,
            last_target_label=target_label or self.last_target_label,
            reason=reason,
        )


class TradeLifecycleEvent(BaseModel):
    """Event input that can replay into a validated lifecycle snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: TradeLifecycleEventType
    occurred_at: datetime
    closed_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    stop_price: float | None = Field(default=None, gt=0)
    trailing_stop_price: float | None = Field(default=None, gt=0)
    target_label: str | None = None
    runner_active: bool | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_event(self) -> TradeLifecycleEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("lifecycle event time must be timezone-aware")
        if self.event_type is TradeLifecycleEventType.PARTIAL_TARGET_HIT and (
            self.closed_percentage is None or not 0 < self.closed_percentage < 100
        ):
            raise ValueError("partial target events require closed_percentage between 0 and 100")
        if (
            self.event_type is TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN
            and self.stop_price is None
        ):
            raise ValueError("stop movement events require stop_price")
        if (
            self.event_type is TradeLifecycleEventType.TRAILING_STOP_UPDATED
            and self.trailing_stop_price is None
        ):
            raise ValueError("trailing stop events require trailing_stop_price")
        return self


_EVENT_TRANSITIONS: dict[TradeLifecycleEventType, TradeLifecycleState | None] = {
    TradeLifecycleEventType.SETUP_GENERATED: None,
    TradeLifecycleEventType.WAITING_FOR_ENTRY: TradeLifecycleState.WAITING_FOR_ENTRY,
    TradeLifecycleEventType.ENTRY_FILLED: TradeLifecycleState.ENTERED,
    TradeLifecycleEventType.PARTIAL_TARGET_HIT: TradeLifecycleState.PARTIALLY_CLOSED,
    TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN: None,
    TradeLifecycleEventType.RUNNER_ACTIVATED: None,
    TradeLifecycleEventType.TRAILING_STOP_UPDATED: None,
    TradeLifecycleEventType.MOMENTUM_FAILURE_EXIT: TradeLifecycleState.STOPPED,
    TradeLifecycleEventType.TIME_EXIT: TradeLifecycleState.EXPIRED,
    TradeLifecycleEventType.STRUCTURAL_INVALIDATION: TradeLifecycleState.INVALIDATED,
    TradeLifecycleEventType.EMERGENCY_STOP: TradeLifecycleState.STOPPED,
    TradeLifecycleEventType.FULL_TARGET_HIT: TradeLifecycleState.TARGET_HIT,
    TradeLifecycleEventType.STOPPED_OUT: TradeLifecycleState.STOPPED,
    TradeLifecycleEventType.EXPIRED: TradeLifecycleState.EXPIRED,
    TradeLifecycleEventType.CANCELLED: TradeLifecycleState.CANCELLED,
}


def replay_lifecycle_events(
    *,
    created_at: datetime,
    events: tuple[TradeLifecycleEvent, ...],
) -> TradeLifecycle:
    """Replay lifecycle events through the existing state transition rules."""

    lifecycle = TradeLifecycle(created_at=created_at, updated_at=created_at)
    for event in sorted(events, key=lambda item: item.occurred_at):
        state = _EVENT_TRANSITIONS[event.event_type]
        if state is None:
            if event.occurred_at < lifecycle.updated_at:
                raise ValueError("lifecycle event time cannot move backward")
            lifecycle = _apply_metadata_event(lifecycle, event)
            continue
        lifecycle = lifecycle.transition(
            state,
            at=event.occurred_at,
            closed_percentage=event.closed_percentage,
            active_stop_price=event.stop_price,
            trailing_stop_price=event.trailing_stop_price,
            runner_active=event.runner_active,
            target_label=event.target_label,
            reason=event.reason or event.event_type.value,
        )
    return lifecycle


def _apply_metadata_event(
    lifecycle: TradeLifecycle,
    event: TradeLifecycleEvent,
) -> TradeLifecycle:
    if lifecycle.state in TERMINAL_LIFECYCLE_STATES:
        raise ValueError("terminal lifecycle states cannot accept metadata events")
    if (
        event.event_type
        in {
            TradeLifecycleEventType.RUNNER_ACTIVATED,
            TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN,
            TradeLifecycleEventType.TRAILING_STOP_UPDATED,
        }
        and lifecycle.entered_at is None
    ):
        raise ValueError("trade-management lifecycle events require an entered trade")
    if event.event_type is TradeLifecycleEventType.RUNNER_ACTIVATED:
        return _replace_lifecycle(
            lifecycle,
            {
                "updated_at": event.occurred_at,
                "runner_active": True,
                "reason": event.reason or event.event_type.value,
            },
        )
    if event.event_type is TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN:
        return _replace_lifecycle(
            lifecycle,
            {
                "updated_at": event.occurred_at,
                "active_stop_price": event.stop_price,
                "reason": event.reason or event.event_type.value,
            },
        )
    if event.event_type is TradeLifecycleEventType.TRAILING_STOP_UPDATED:
        return _replace_lifecycle(
            lifecycle,
            {
                "updated_at": event.occurred_at,
                "trailing_stop_price": event.trailing_stop_price,
                "runner_active": True,
                "reason": event.reason or event.event_type.value,
            },
        )
    return _replace_lifecycle(lifecycle, {"updated_at": event.occurred_at})


def _replace_lifecycle(
    lifecycle: TradeLifecycle,
    update: dict[str, object],
) -> TradeLifecycle:
    payload = lifecycle.model_dump()
    payload.update(update)
    return TradeLifecycle(**payload)
