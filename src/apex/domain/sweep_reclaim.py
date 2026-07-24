"""Shared deterministic sweep/reclaim qualification.

This module contains no backtest or presentation authority. It evaluates only
closed-candle path facts so backtesting and production reconstruction can share
the same qualification rules without future-label leakage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from apex.domain.models import Candle
from apex.strategies import TradeDirection


@dataclass(frozen=True, slots=True)
class SweepReclaimPolicy:
    """Thresholds for classifying a stop sweep and subsequent reclaim."""

    shallow_breach_max_r: float = 0.25
    deep_breach_min_r: float = 0.60
    deep_close_min_r: float = 0.35
    shallow_reclaim_max_bars: int = 2
    deep_reclaim_bars: int = 4
    deep_consecutive_closes: int = 2
    reclaim_body_ratio_min: float = 0.40
    reclaim_close_location_min: float = 0.65
    reclaim_max_confirm_bars: int = 2
    minimum_remaining_target_r: float = 1.00

    def __post_init__(self) -> None:
        non_negative = (
            self.shallow_breach_max_r,
            self.deep_breach_min_r,
            self.deep_close_min_r,
            self.reclaim_body_ratio_min,
            self.reclaim_close_location_min,
            self.minimum_remaining_target_r,
        )
        if any(value < 0.0 for value in non_negative):
            raise ValueError("sweep/reclaim policy thresholds cannot be negative")
        if self.deep_breach_min_r < self.shallow_breach_max_r:
            raise ValueError("deep breach threshold cannot be below shallow breach threshold")
        if self.shallow_reclaim_max_bars < 0:
            raise ValueError("shallow reclaim bars cannot be negative")
        if self.deep_reclaim_bars < self.shallow_reclaim_max_bars:
            raise ValueError("deep reclaim bars cannot be below shallow reclaim bars")
        if self.deep_consecutive_closes < 1:
            raise ValueError("deep consecutive closes must be positive")
        if self.reclaim_max_confirm_bars < 1:
            raise ValueError("reclaim confirmation window must be positive")
        if self.reclaim_body_ratio_min > 1.0:
            raise ValueError("reclaim body ratio cannot exceed one")
        if self.reclaim_close_location_min > 1.0:
            raise ValueError("reclaim close location cannot exceed one")


DEFAULT_SWEEP_RECLAIM_POLICY = SweepReclaimPolicy()


class SweepReclaimState(StrEnum):
    INVALID_GEOMETRY = "invalid_geometry"
    NOT_A_SWEEP = "not_a_sweep"
    SHALLOW_SWEEP_PENDING = "shallow_sweep_pending"
    RECLAIM_CONFIRMED = "reclaim_confirmed"
    RETEST_CONFIRMED = "retest_confirmed"
    DEEP_FAILURE = "deep_failure"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SweepReclaimAssessment:
    """Decision-time-safe sweep/reclaim path assessment."""

    state: SweepReclaimState
    shallow_sweep: bool
    wick_only_sweep: bool
    deep_failure: bool
    sweep_candidate: bool
    reclaim_confirmed: bool
    entry_level_held_next_candle: bool
    retest_available: bool
    retest_held: bool
    structure_confirmed: bool
    maximum_breach_r: float
    maximum_close_breach_r: float
    bars_closed_beyond_invalidation: int
    maximum_consecutive_closes_beyond_invalidation: int
    bars_to_invalidation_reclaim: int | None
    bars_to_entry_reclaim: int | None
    reclaim_body_ratio: float
    reclaim_close_location: float
    remaining_target_room_r: float
    reclaim_entry_price: float | None
    reclaim_candle_index: int | None
    rejected_reason: str

    @property
    def retest_confirmed(self) -> bool:
        """Backward-compatible alias for the held-retest fact."""

        return self.retest_held

    @property
    def recovery_entry_authorized(self) -> bool:
        return self.reclaim_confirmed and self.structure_confirmed and not self.deep_failure


def evaluate_sweep_reclaim(
    *,
    direction: TradeDirection,
    entry_price: float,
    invalidation_price: float,
    target_price: float,
    sweep_candle: Candle,
    confirmation_candles: Sequence[Candle],
    policy: SweepReclaimPolicy = DEFAULT_SWEEP_RECLAIM_POLICY,
) -> SweepReclaimAssessment:
    """Evaluate a possible sweep using only currently available closed candles.

    The computation order intentionally mirrors the legacy backtest diagnostic:
    all reclaim, hold, retest, and remaining-room facts are calculated before the
    final classification is selected. This keeps the shared evaluator suitable
    for parity validation while avoiding any future trade-outcome labels.
    """

    risk = abs(entry_price - invalidation_price)
    if risk <= 0.0:
        return _assessment(
            state=SweepReclaimState.INVALID_GEOMETRY,
            rejected_reason="invalid_risk_geometry",
        )

    all_breach_candles = (sweep_candle, *confirmation_candles)

    def breach_r(candle: Candle) -> float:
        if direction is TradeDirection.LONG:
            return max(0.0, invalidation_price - candle.low) / risk
        return max(0.0, candle.high - invalidation_price) / risk

    def close_breach_r(candle: Candle) -> float:
        if direction is TradeDirection.LONG:
            return max(0.0, invalidation_price - candle.close) / risk
        return max(0.0, candle.close - invalidation_price) / risk

    def traded_beyond(candle: Candle) -> bool:
        if direction is TradeDirection.LONG:
            return candle.low < invalidation_price
        return candle.high > invalidation_price

    def closed_beyond(candle: Candle) -> bool:
        if direction is TradeDirection.LONG:
            return candle.close < invalidation_price
        return candle.close > invalidation_price

    def invalidation_reclaimed(candle: Candle) -> bool:
        if direction is TradeDirection.LONG:
            return candle.close >= invalidation_price
        return candle.close <= invalidation_price

    def entry_reclaimed(candle: Candle) -> bool:
        if direction is TradeDirection.LONG:
            return candle.close >= entry_price
        return candle.close <= entry_price

    def entry_touched(candle: Candle) -> bool:
        return candle.low <= entry_price <= candle.high

    def favorable_close(candle: Candle, level: float) -> bool:
        if direction is TradeDirection.LONG:
            return candle.close >= level
        return candle.close <= level

    maximum_breach_r = max(breach_r(candle) for candle in all_breach_candles)
    maximum_close_breach_r = max(close_breach_r(candle) for candle in all_breach_candles)
    bars_traded_beyond = sum(traded_beyond(candle) for candle in all_breach_candles)
    bars_closed_beyond = sum(closed_beyond(candle) for candle in all_breach_candles)

    consecutive = 0
    maximum_consecutive = 0
    for candle in all_breach_candles:
        if closed_beyond(candle):
            consecutive += 1
            maximum_consecutive = max(maximum_consecutive, consecutive)
        else:
            consecutive = 0

    bars_to_invalidation_reclaim = 0
    bars_to_entry_reclaim = 0
    invalidation_was_reclaimed = invalidation_reclaimed(sweep_candle)
    entry_was_reclaimed = entry_reclaimed(sweep_candle)
    reclaim_candle: Candle | None = None
    reclaim_index = 0

    for index, candle in enumerate(confirmation_candles, start=1):
        if not invalidation_was_reclaimed and invalidation_reclaimed(candle):
            invalidation_was_reclaimed = True
            bars_to_invalidation_reclaim = index
        if not entry_was_reclaimed and entry_reclaimed(candle):
            entry_was_reclaimed = True
            bars_to_entry_reclaim = index
        if reclaim_candle is None and entry_reclaimed(candle):
            reclaim_candle = candle
            reclaim_index = index

    stop_candle_reclaimed = invalidation_reclaimed(sweep_candle)
    wick_only_sweep = (
        maximum_breach_r > policy.shallow_breach_max_r
        and close_breach_r(sweep_candle) == 0.0
        and stop_candle_reclaimed
        and bars_closed_beyond == 0
    )
    close_failure = (
        maximum_close_breach_r >= policy.deep_close_min_r
        or maximum_consecutive >= policy.deep_consecutive_closes
    )
    slow_or_failed_reclaim = (
        not invalidation_was_reclaimed
        or bars_to_invalidation_reclaim > policy.deep_reclaim_bars
    )
    deep_failure = close_failure or (
        maximum_breach_r >= policy.deep_breach_min_r
        and not wick_only_sweep
        and slow_or_failed_reclaim
    )
    shallow_sweep = (
        not deep_failure
        and maximum_breach_r <= policy.shallow_breach_max_r
        and bars_closed_beyond <= 1
        and invalidation_was_reclaimed
        and (
            stop_candle_reclaimed
            or 0 < bars_to_invalidation_reclaim <= policy.shallow_reclaim_max_bars
        )
    )
    sweep_candidate = not deep_failure and (shallow_sweep or wick_only_sweep)

    reclaim_body_ratio = 0.0
    reclaim_close_location = 0.0
    remaining_target_room_r = 0.0
    reclaim_entry_price: float | None = None
    entry_level_held_next_candle = False
    retest_available = False
    retest_held = False

    if reclaim_candle is not None:
        candle_range = reclaim_candle.high - reclaim_candle.low
        if candle_range > 0.0:
            reclaim_body_ratio = abs(reclaim_candle.close - reclaim_candle.open) / candle_range
            if direction is TradeDirection.LONG:
                reclaim_close_location = (
                    reclaim_candle.close - reclaim_candle.low
                ) / candle_range
            else:
                reclaim_close_location = (
                    reclaim_candle.high - reclaim_candle.close
                ) / candle_range

        reclaim_entry_price = reclaim_candle.close
        remaining_target_room_r = (
            (target_price - reclaim_entry_price) / risk
            if direction is TradeDirection.LONG
            else (reclaim_entry_price - target_price) / risk
        )

        next_index = reclaim_index
        if next_index < len(confirmation_candles):
            next_candle = confirmation_candles[next_index]
            entry_level_held_next_candle = favorable_close(next_candle, entry_price)

        for later in confirmation_candles[reclaim_index:]:
            if closed_beyond(later):
                break
            if entry_touched(later):
                retest_available = True
                if favorable_close(later, entry_price):
                    retest_held = True

    strong_reclaim = (
        reclaim_candle is not None
        and reclaim_body_ratio >= policy.reclaim_body_ratio_min
        and reclaim_close_location >= policy.reclaim_close_location_min
    )
    timely_reclaim = 0 < reclaim_index <= policy.reclaim_max_confirm_bars
    structure_confirmed = entry_level_held_next_candle or retest_held
    reclaim_confirmed = (
        sweep_candidate
        and timely_reclaim
        and strong_reclaim
        and remaining_target_room_r >= policy.minimum_remaining_target_r
    )

    if deep_failure:
        rejected_reason = "deep_directional_failure"
        state = SweepReclaimState.DEEP_FAILURE
    elif not sweep_candidate:
        rejected_reason = "not_a_sweep_candidate"
        state = SweepReclaimState.NOT_A_SWEEP
    elif reclaim_candle is None:
        rejected_reason = "entry_level_not_reclaimed"
        state = SweepReclaimState.SHALLOW_SWEEP_PENDING
    elif not timely_reclaim:
        rejected_reason = "reclaim_too_slow"
        state = SweepReclaimState.EXPIRED
    elif not strong_reclaim:
        rejected_reason = "weak_reclaim_candle"
        state = SweepReclaimState.SHALLOW_SWEEP_PENDING
    elif remaining_target_room_r < policy.minimum_remaining_target_r:
        rejected_reason = "insufficient_remaining_target_room"
        state = SweepReclaimState.NOT_A_SWEEP
    elif not structure_confirmed:
        rejected_reason = "reclaim_not_held_or_retested"
        state = SweepReclaimState.RECLAIM_CONFIRMED
    else:
        rejected_reason = "none"
        state = SweepReclaimState.RETEST_CONFIRMED

    return _assessment(
        state=state,
        shallow_sweep=shallow_sweep,
        wick_only_sweep=wick_only_sweep,
        deep_failure=deep_failure,
        sweep_candidate=sweep_candidate,
        reclaim_confirmed=reclaim_confirmed,
        entry_level_held_next_candle=entry_level_held_next_candle,
        retest_available=retest_available,
        retest_held=retest_held,
        structure_confirmed=structure_confirmed,
        maximum_breach_r=maximum_breach_r,
        maximum_close_breach_r=maximum_close_breach_r,
        bars_traded_beyond_invalidation=bars_traded_beyond,
        bars_closed_beyond_invalidation=bars_closed_beyond,
        maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
        bars_to_invalidation_reclaim=(
            bars_to_invalidation_reclaim if invalidation_was_reclaimed else None
        ),
        bars_to_entry_reclaim=(bars_to_entry_reclaim if entry_was_reclaimed else None),
        reclaim_body_ratio=reclaim_body_ratio,
        reclaim_close_location=reclaim_close_location,
        remaining_target_room_r=remaining_target_room_r,
        reclaim_entry_price=reclaim_entry_price,
        reclaim_candle_index=(reclaim_index if reclaim_candle is not None else None),
        rejected_reason=rejected_reason,
    )


def _assessment(
    *,
    state: SweepReclaimState,
    shallow_sweep: bool = False,
    wick_only_sweep: bool = False,
    deep_failure: bool = False,
    sweep_candidate: bool = False,
    reclaim_confirmed: bool = False,
    entry_level_held_next_candle: bool = False,
    retest_available: bool = False,
    retest_held: bool = False,
    structure_confirmed: bool = False,
    maximum_breach_r: float = 0.0,
    maximum_close_breach_r: float = 0.0,
    bars_traded_beyond_invalidation: int = 0,
    bars_closed_beyond_invalidation: int = 0,
    maximum_consecutive_closes_beyond_invalidation: int = 0,
    bars_to_invalidation_reclaim: int | None = None,
    bars_to_entry_reclaim: int | None = None,
    reclaim_body_ratio: float = 0.0,
    reclaim_close_location: float = 0.0,
    remaining_target_room_r: float = 0.0,
    reclaim_entry_price: float | None = None,
    reclaim_candle_index: int | None = None,
    rejected_reason: str,
) -> SweepReclaimAssessment:
    del bars_traded_beyond_invalidation
    return SweepReclaimAssessment(
        state=state,
        shallow_sweep=shallow_sweep,
        wick_only_sweep=wick_only_sweep,
        deep_failure=deep_failure,
        sweep_candidate=sweep_candidate,
        reclaim_confirmed=reclaim_confirmed,
        entry_level_held_next_candle=entry_level_held_next_candle,
        retest_available=retest_available,
        retest_held=retest_held,
        structure_confirmed=structure_confirmed,
        maximum_breach_r=maximum_breach_r,
        maximum_close_breach_r=maximum_close_breach_r,
        bars_closed_beyond_invalidation=bars_closed_beyond_invalidation,
        maximum_consecutive_closes_beyond_invalidation=(
            maximum_consecutive_closes_beyond_invalidation
        ),
        bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
        bars_to_entry_reclaim=bars_to_entry_reclaim,
        reclaim_body_ratio=reclaim_body_ratio,
        reclaim_close_location=reclaim_close_location,
        remaining_target_room_r=remaining_target_room_r,
        reclaim_entry_price=reclaim_entry_price,
        reclaim_candle_index=reclaim_candle_index,
        rejected_reason=rejected_reason,
    )
