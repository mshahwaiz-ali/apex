"""Deterministic replay for spot trade lifecycle events."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.spot import SpotLifecycleSnapshot, SpotLifecycleState


class SpotLifecycleEventType(StrEnum):
    ENTRY_FILLED = "ENTRY_FILLED"
    TARGET_FILLED = "TARGET_FILLED"
    STOP_FILLED = "STOP_FILLED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"


class SpotLifecycleEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: SpotLifecycleEventType
    label: str | None = None
    quantity: float = Field(default=0.0, ge=0)
    stop_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.event_type in {
            SpotLifecycleEventType.ENTRY_FILLED,
            SpotLifecycleEventType.TARGET_FILLED,
        } and (not self.label or self.quantity <= 0):
            raise ValueError("fill events require label and positive quantity")
        return self


def replay_spot_lifecycle(
    events: tuple[SpotLifecycleEvent, ...],
    *,
    initial_stop_price: float | None = None,
) -> SpotLifecycleSnapshot:
    state = SpotLifecycleState.WAITING_FOR_ENTRY
    entries: list[str] = []
    targets: list[str] = []
    open_quantity = 0.0
    active_stop = initial_stop_price

    for event in events:
        if state in {
            SpotLifecycleState.CLOSED,
            SpotLifecycleState.STOPPED,
            SpotLifecycleState.EXPIRED,
            SpotLifecycleState.CANCELLED,
            SpotLifecycleState.INVALIDATED,
        }:
            raise ValueError("terminal spot lifecycle cannot accept further events")
        if event.stop_price is not None:
            active_stop = event.stop_price
        if event.event_type is SpotLifecycleEventType.ENTRY_FILLED:
            if event.label in entries:
                raise ValueError("spot entry cannot be filled twice")
            entries.append(event.label or "")
            open_quantity += event.quantity
            state = SpotLifecycleState.PARTIALLY_FILLED
        elif event.event_type is SpotLifecycleEventType.TARGET_FILLED:
            if open_quantity <= 0 or event.quantity > open_quantity:
                raise ValueError("spot target fill exceeds open quantity")
            if event.label in targets:
                raise ValueError("spot target cannot be filled twice")
            targets.append(event.label or "")
            open_quantity -= event.quantity
            state = (
                SpotLifecycleState.CLOSED
                if open_quantity == 0
                else SpotLifecycleState.PARTIALLY_REDUCED
            )
        elif event.event_type is SpotLifecycleEventType.STOP_FILLED:
            open_quantity = 0.0
            state = SpotLifecycleState.STOPPED
        elif event.event_type is SpotLifecycleEventType.EXPIRED:
            if open_quantity != 0:
                raise ValueError("active spot position cannot expire")
            state = SpotLifecycleState.EXPIRED
        elif event.event_type is SpotLifecycleEventType.CANCELLED:
            if open_quantity != 0:
                raise ValueError("active spot position cannot be cancelled")
            state = SpotLifecycleState.CANCELLED
        elif event.event_type is SpotLifecycleEventType.INVALIDATED:
            open_quantity = 0.0
            state = SpotLifecycleState.INVALIDATED

    return SpotLifecycleSnapshot(
        state=state,
        filled_entry_labels=tuple(entries),
        completed_target_labels=tuple(targets),
        open_quantity=open_quantity,
        active_stop_price=active_stop,
    )
