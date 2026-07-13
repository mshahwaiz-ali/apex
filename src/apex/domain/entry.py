"""Canonical direction-aware entry-state classification."""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.futures import EntryState, FuturesDirection

BOUNDARY_POLICY = (
    "Entry-zone, reclaim, retest, chase, and invalidation boundaries are inclusive "
    "within the configured tolerance."
)


class EntryClassificationInput(BaseModel):
    """Validated geometry used to classify the actionable futures entry state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: FuturesDirection
    current_price: float = Field(gt=0)
    zone_low: float = Field(gt=0)
    zone_high: float = Field(gt=0)
    ideal_entry: float = Field(gt=0)
    maximum_chase_price: float = Field(gt=0)
    reclaim_trigger: float | None = Field(default=None, gt=0)
    retest_trigger: float | None = Field(default=None, gt=0)
    structural_invalidation: float | None = Field(default=None, gt=0)
    setup_eligible: bool = True
    geometry_complete: bool = True
    tolerance: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        for name, value in (
            ("current_price", self.current_price),
            ("zone_low", self.zone_low),
            ("zone_high", self.zone_high),
            ("ideal_entry", self.ideal_entry),
            ("maximum_chase_price", self.maximum_chase_price),
            ("tolerance", self.tolerance),
        ):
            _finite(name, value)
        for name, optional_value in (
            ("reclaim_trigger", self.reclaim_trigger),
            ("retest_trigger", self.retest_trigger),
            ("structural_invalidation", self.structural_invalidation),
        ):
            if optional_value is not None:
                _finite(name, optional_value)
        if self.zone_low > self.zone_high:
            raise ValueError("entry zone low cannot exceed entry zone high")
        if not self.zone_low <= self.ideal_entry <= self.zone_high:
            raise ValueError("ideal entry must remain inside the entry zone")
        if self.direction is FuturesDirection.LONG:
            if self.maximum_chase_price < self.zone_high:
                raise ValueError("long maximum chase price cannot be below the entry-zone high")
        elif self.maximum_chase_price > self.zone_low:
            raise ValueError("short maximum chase price cannot be above the entry-zone low")
        return self


class EntryClassificationResult(BaseModel):
    """Canonical entry-state result consumed by output and execution layers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: EntryState
    reasons: tuple[str, ...]
    boundary_policy: str = BOUNDARY_POLICY


def classify_entry_state(geometry: EntryClassificationInput) -> EntryClassificationResult:
    """Classify entry actionability using deterministic precedence."""

    if not geometry.setup_eligible:
        return _result(EntryState.NO_TRADE, "setup is not eligible")
    if not geometry.geometry_complete:
        return _result(EntryState.NO_TRADE, "entry geometry is incomplete")

    if _is_invalidated(geometry):
        return _result(EntryState.INVALIDATED, "current price touched structural invalidation")
    if _is_missed(geometry):
        return _result(EntryState.MISSED_ENTRY, "current price moved beyond maximum chase")
    if _inside_zone(geometry):
        return _result(EntryState.READY_NOW, "current price is inside the entry zone")
    if _needs_retest(geometry):
        return _result(EntryState.WAIT_FOR_RETEST, "current price requires an entry-zone retest")
    if _needs_reclaim(geometry):
        return _result(EntryState.WAIT_FOR_RECLAIM, "current price requires reclaim before entry")
    if _approaching_entry(geometry):
        return _result(EntryState.APPROACHING_ENTRY, "current price is approaching the entry zone")
    return _result(EntryState.WATCH, "valid setup is not close enough for an actionable state")


def _result(state: EntryState, reason: str) -> EntryClassificationResult:
    return EntryClassificationResult(state=state, reasons=(reason,))


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _lte(lhs: float, rhs: float, tolerance: float) -> bool:
    return lhs <= rhs + tolerance


def _gte(lhs: float, rhs: float, tolerance: float) -> bool:
    return lhs >= rhs - tolerance


def _inside_zone(geometry: EntryClassificationInput) -> bool:
    return _gte(geometry.current_price, geometry.zone_low, geometry.tolerance) and _lte(
        geometry.current_price, geometry.zone_high, geometry.tolerance
    )


def _is_invalidated(geometry: EntryClassificationInput) -> bool:
    if geometry.structural_invalidation is None:
        return False
    if geometry.direction is FuturesDirection.LONG:
        return _lte(geometry.current_price, geometry.structural_invalidation, geometry.tolerance)
    return _gte(geometry.current_price, geometry.structural_invalidation, geometry.tolerance)


def _is_missed(geometry: EntryClassificationInput) -> bool:
    if geometry.direction is FuturesDirection.LONG:
        return geometry.current_price > geometry.maximum_chase_price + geometry.tolerance
    return geometry.current_price < geometry.maximum_chase_price - geometry.tolerance


def _needs_retest(geometry: EntryClassificationInput) -> bool:
    if geometry.direction is FuturesDirection.LONG:
        if not (
            geometry.current_price > geometry.zone_high + geometry.tolerance
            and _lte(geometry.current_price, geometry.maximum_chase_price, geometry.tolerance)
        ):
            return False
        return geometry.retest_trigger is None or _gte(
            geometry.current_price, geometry.retest_trigger, geometry.tolerance
        )
    if not (
        geometry.current_price < geometry.zone_low - geometry.tolerance
        and _gte(geometry.current_price, geometry.maximum_chase_price, geometry.tolerance)
    ):
        return False
    return geometry.retest_trigger is None or _lte(
        geometry.current_price, geometry.retest_trigger, geometry.tolerance
    )


def _needs_reclaim(geometry: EntryClassificationInput) -> bool:
    if geometry.reclaim_trigger is None:
        return False
    if geometry.direction is FuturesDirection.LONG:
        return geometry.current_price < geometry.zone_low - geometry.tolerance and _lte(
            geometry.current_price, geometry.reclaim_trigger, geometry.tolerance
        )
    return geometry.current_price > geometry.zone_high + geometry.tolerance and _gte(
        geometry.current_price, geometry.reclaim_trigger, geometry.tolerance
    )


def _approaching_entry(geometry: EntryClassificationInput) -> bool:
    if geometry.direction is FuturesDirection.LONG:
        return geometry.current_price < geometry.zone_low - geometry.tolerance
    return geometry.current_price > geometry.zone_high + geometry.tolerance
