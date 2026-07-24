"""Shared deterministic sweep/reclaim qualification.

This module contains no backtest or presentation authority.  It evaluates only
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
    reclaim_confirmed: bool
    retest_confirmed: bool
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
    def recovery_entry_authorized(self) -> bool:
        return self.state is SweepReclaimState.RETEST_CONFIRMED


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
    """Evaluate a possible sweep using only candles available through confirmation.

    ``sweep_candle`` is the candle that first traded through invalidation.
    ``confirmation_candles`` must contain only subsequent closed candles known at
    the evaluation time.  The function does not inspect later trade outcomes.
    """

    risk = abs(entry_price - invalidation_price)
    if risk <= 0.0:
        return _assessment(
            state=SweepReclaimState.INVALID_GEOMETRY,
            rejected_reason="invalid_risk_geometry",
        )

    candles = (sweep_candle, *confirmation_candles)

    def breach_r(candle: Candle) -> float:
        if direction is TradeDirection.LONG:
            return max(0.0, invalidation_price - candle.low) / risk
        return max(0.0, candle.high - invalidation_price) / risk

    def close_breach_r(candle: Candle) -> float:
        if direction is TradeDirection.LONG:
            return max(0.0, invalidation_price - candle.close) / risk
        return max(0.0, candle.close - invalidation_price) / risk

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

    maximum_breach_r = max(breach_r(candle) for candle in candles)
    maximum_close_breach_r = max(close_breach_r(candle) for candle in candles)
    bars_closed_beyond = sum(closed_beyond(candle) for candle in candles)

    consecutive = 0
    maximum_consecutive = 0
    for candle in candles:
        if closed_beyond(candle):
            consecutive += 1
            maximum_consecutive = max(maximum_consecutive, consecutive)
        else:
            consecutive = 0

    bars_to_invalidation_reclaim: int | None = 0 if invalidation_reclaimed(sweep_candle) else None
    bars_to_entry_reclaim: int | None = 0 if entry_reclaimed(sweep_candle) else None
    reclaim_candle: Candle | None = sweep_candle if entry_reclaimed(sweep_candle) else None
    reclaim_index: int | None = 0 if reclaim_candle is not None else None

    for index, candle in enumerate(confirmation_candles, start=1):
        if bars_to_invalidation_reclaim is None and invalidation_reclaimed(candle):
            bars_to_invalidation_reclaim = index
        if bars_to_entry_reclaim is None and entry_reclaimed(candle):
            bars_to_entry_reclaim = index
            reclaim_candle = candle
            reclaim_index = index

    wick_only_sweep = (
        maximum_breach_r > policy.shallow_breach_max_r
        and close_breach_r(sweep_candle) == 0.0
        and invalidation_reclaimed(sweep_candle)
        and bars_closed_beyond == 0
    )
    close_failure = (
        maximum_close_breach_r >= policy.deep_close_min_r
        or maximum_consecutive >= policy.deep_consecutive_closes
    )
    slow_or_failed_reclaim = (
        bars_to_invalidation_reclaim is None
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
        and bars_to_invalidation_reclaim is not None
        and bars_to_invalidation_reclaim <= policy.shallow_reclaim_max_bars
    )
    sweep_candidate = not deep_failure and (shallow_sweep or wick_only_sweep)

    if deep_failure:
        return _assessment(
            state=SweepReclaimState.DEEP_FAILURE,
            deep_failure=True,
            wick_only_sweep=wick_only_sweep,
            maximum_breach_r=maximum_breach_r,
            maximum_close_breach_r=maximum_close_breach_r,
            bars_closed_beyond_invalidation=bars_closed_beyond,
            maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
            bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
            bars_to_entry_reclaim=bars_to_entry_reclaim,
            rejected_reason="deep_directional_failure",
        )
    if not sweep_candidate:
        return _assessment(
            state=SweepReclaimState.NOT_A_SWEEP,
            maximum_breach_r=maximum_breach_r,
            maximum_close_breach_r=maximum_close_breach_r,
            bars_closed_beyond_invalidation=bars_closed_beyond,
            maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
            bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
            bars_to_entry_reclaim=bars_to_entry_reclaim,
            rejected_reason="not_a_sweep_candidate",
        )
    if reclaim_candle is None or reclaim_index is None:
        return _assessment(
            state=SweepReclaimState.SHALLOW_SWEEP_PENDING,
            shallow_sweep=shallow_sweep,
            wick_only_sweep=wick_only_sweep,
            maximum_breach_r=maximum_breach_r,
            maximum_close_breach_r=maximum_close_breach_r,
            bars_closed_beyond_invalidation=bars_closed_beyond,
            maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
            bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
            rejected_reason="entry_level_not_reclaimed",
        )

    candle_range = reclaim_candle.high - reclaim_candle.low
    body_ratio = 0.0
    close_location = 0.0
    if candle_range > 0.0:
        body_ratio = abs(reclaim_candle.close - reclaim_candle.open) / candle_range
        if direction is TradeDirection.LONG:
            close_location = (reclaim_candle.close - reclaim_candle.low) / candle_range
        else:
            close_location = (reclaim_candle.high - reclaim_candle.close) / candle_range

    remaining_target_room_r = (
        (target_price - reclaim_candle.close) / risk
        if direction is TradeDirection.LONG
        else (reclaim_candle.close - target_price) / risk
    )
    timely = reclaim_index <= policy.reclaim_max_confirm_bars
    strong = (
        body_ratio >= policy.reclaim_body_ratio_min
        and close_location >= policy.reclaim_close_location_min
    )
    confirmed = timely and strong and remaining_target_room_r >= policy.minimum_remaining_target_r

    if not confirmed:
        if not timely:
            reason = "reclaim_too_slow"
            state = SweepReclaimState.EXPIRED
        elif not strong:
            reason = "weak_reclaim_candle"
            state = SweepReclaimState.SHALLOW_SWEEP_PENDING
        else:
            reason = "insufficient_remaining_target_room"
            state = SweepReclaimState.NOT_A_SWEEP
        return _assessment(
            state=state,
            shallow_sweep=shallow_sweep,
            wick_only_sweep=wick_only_sweep,
            maximum_breach_r=maximum_breach_r,
            maximum_close_breach_r=maximum_close_breach_r,
            bars_closed_beyond_invalidation=bars_closed_beyond,
            maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
            bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
            bars_to_entry_reclaim=bars_to_entry_reclaim,
            reclaim_body_ratio=body_ratio,
            reclaim_close_location=close_location,
            remaining_target_room_r=remaining_target_room_r,
            reclaim_entry_price=reclaim_candle.close,
            reclaim_candle_index=reclaim_index,
            rejected_reason=reason,
        )

    retest_confirmed = False
    for candle in confirmation_candles[reclaim_index:]:
        if closed_beyond(candle):
            break
        if entry_touched(candle) and entry_reclaimed(candle):
            retest_confirmed = True
            break

    return _assessment(
        state=(
            SweepReclaimState.RETEST_CONFIRMED
            if retest_confirmed
            else SweepReclaimState.RECLAIM_CONFIRMED
        ),
        shallow_sweep=shallow_sweep,
        wick_only_sweep=wick_only_sweep,
        reclaim_confirmed=True,
        retest_confirmed=retest_confirmed,
        maximum_breach_r=maximum_breach_r,
        maximum_close_breach_r=maximum_close_breach_r,
        bars_closed_beyond_invalidation=bars_closed_beyond,
        maximum_consecutive_closes_beyond_invalidation=maximum_consecutive,
        bars_to_invalidation_reclaim=bars_to_invalidation_reclaim,
        bars_to_entry_reclaim=bars_to_entry_reclaim,
        reclaim_body_ratio=body_ratio,
        reclaim_close_location=close_location,
        remaining_target_room_r=remaining_target_room_r,
        reclaim_entry_price=reclaim_candle.close,
        reclaim_candle_index=reclaim_index,
        rejected_reason="none" if retest_confirmed else "reclaim_not_retested",
    )


def _assessment(
    *,
    state: SweepReclaimState,
    shallow_sweep: bool = False,
    wick_only_sweep: bool = False,
    deep_failure: bool = False,
    reclaim_confirmed: bool = False,
    retest_confirmed: bool = False,
    maximum_breach_r: float = 0.0,
    maximum_close_breach_r: float = 0.0,
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
    return SweepReclaimAssessment(
        state=state,
        shallow_sweep=shallow_sweep,
        wick_only_sweep=wick_only_sweep,
        deep_failure=deep_failure,
        reclaim_confirmed=reclaim_confirmed,
        retest_confirmed=retest_confirmed,
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
