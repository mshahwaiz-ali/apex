"""Validated lifecycle state machine for futures trade plans."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.futures import TradeLifecycleState


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
    reason: str | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
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
        if self.state in {
            TradeLifecycleState.ENTERED,
            TradeLifecycleState.PARTIALLY_CLOSED,
            TradeLifecycleState.STOPPED,
            TradeLifecycleState.TARGET_HIT,
        } and self.entered_at is None:
            raise ValueError(f"{self.state.value} requires entered_at")
        if self.state is TradeLifecycleState.PARTIALLY_CLOSED and not 0 < self.closed_percentage < 100:
            raise ValueError("PARTIALLY_CLOSED requires closed_percentage between zero and 100")
        if self.state is TradeLifecycleState.TARGET_HIT and self.closed_percentage != 100:
            raise ValueError("TARGET_HIT requires closed_percentage equal to 100")
        if self.state in TERMINAL_LIFECYCLE_STATES and self.closed_at is None:
            raise ValueError(f"{self.state.value} requires closed_at")
        if self.state not in TERMINAL_LIFECYCLE_STATES and self.closed_at is not None:
            raise ValueError("non-terminal lifecycle state cannot have closed_at")
        return self

    def transition(
        self,
        state: TradeLifecycleState,
        *,
        at: datetime,
        closed_percentage: float | None = None,
        reason: str | None = None,
    ) -> Self:
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

        closed_at = at if state in TERMINAL_LIFECYCLE_STATES else None
        return TradeLifecycle(
            state=state,
            created_at=self.created_at,
            updated_at=at,
            entered_at=entered_at,
            closed_at=closed_at,
            closed_percentage=next_closed_percentage,
            reason=reason,
        )
