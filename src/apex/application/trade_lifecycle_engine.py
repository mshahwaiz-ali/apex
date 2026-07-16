"""Replay candle observations through canonical futures lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apex.domain import (
    FuturesDirection,
    TradeLifecycle,
    TradeLifecycleEvent,
    TradeLifecycleEventType,
    TradeManagementPlan,
    replay_lifecycle_events,
)


@dataclass(frozen=True, slots=True)
class LifecycleObservation:
    observed_at: datetime
    high: float
    low: float
    close: float
    momentum_failed: bool = False
    fast_failure: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("lifecycle observation time must be timezone-aware")
        if self.low <= 0.0 or self.high <= 0.0 or self.close <= 0.0:
            raise ValueError("lifecycle observation prices must be positive")
        if self.low > self.high or not self.low <= self.close <= self.high:
            raise ValueError("lifecycle observation geometry is invalid")


@dataclass(frozen=True, slots=True)
class TradeLifecycleExecution:
    lifecycle: TradeLifecycle
    entry_price: float | None
    exit_price: float | None
    remaining_percentage: float
    realized_pnl: float
    unrealized_pnl: float
    total_fees: float
    total_slippage: float
    realized_r_multiple: float
    bars_pending: int
    bars_open: int
    events: tuple[TradeLifecycleEvent, ...]
    exit_reason: str | None


def replay_trade_lifecycle(
    plan: TradeManagementPlan,
    observations: tuple[LifecycleObservation, ...],
    *,
    created_at: datetime,
    fee_rate: float = 0.0,
    slippage_rate: float = 0.0,
    maximum_pending_bars: int = 15,
    maximum_open_bars: int = 60,
    trailing_distance_rate: float = 0.005,
) -> TradeLifecycleExecution:
    """Replay one management plan using conservative intrabar ordering."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("lifecycle creation time must be timezone-aware")
    if fee_rate < 0.0 or slippage_rate < 0.0 or trailing_distance_rate < 0.0:
        raise ValueError("lifecycle execution rates cannot be negative")
    if maximum_pending_bars <= 0 or maximum_open_bars <= 0:
        raise ValueError("lifecycle bar limits must be positive")

    ordered = tuple(sorted(observations, key=lambda item: item.observed_at))
    events: list[TradeLifecycleEvent] = []
    entry_price: float | None = None
    exit_price: float | None = None
    remaining = 100.0
    realized = fees = slippage = 0.0
    bars_pending = bars_open = 0
    active_stop = plan.initial_protection.stop_loss_price
    targets_hit: set[str] = set()
    runner_active = False
    exit_reason: str | None = None

    for observation in ordered:
        if exit_reason is not None:
            break
        if entry_price is None:
            bars_pending += 1
            if _stop_touched(plan.direction, observation, active_stop):
                events.append(
                    _event(
                        TradeLifecycleEventType.STRUCTURAL_INVALIDATION,
                        observation.observed_at,
                        reason="structural invalidation occurred before entry",
                    )
                )
                exit_reason = "structural invalidation before entry"
                continue
            if _entry_touched(plan, observation):
                entry_price = _entry_fill_price(plan, slippage_rate)
                fees += entry_price * plan.initial_protection.quantity * fee_rate
                slippage += abs(entry_price - plan.entry.ideal_entry) * plan.initial_protection.quantity
                events.append(_event(TradeLifecycleEventType.ENTRY_FILLED, observation.observed_at))
                bars_open = 1
            elif bars_pending >= maximum_pending_bars:
                events.append(
                    _event(
                        TradeLifecycleEventType.EXPIRED,
                        observation.observed_at,
                        reason="entry did not fill before pending-bar limit",
                    )
                )
                exit_reason = "entry expired"
            continue

        bars_open += 1
        if _stop_touched(plan.direction, observation, active_stop):
            exit_price = _exit_fill_price(plan.direction, active_stop, slippage_rate)
            realized += _pnl(plan, entry_price, exit_price, remaining)
            fees += exit_price * _quantity(plan, remaining) * fee_rate
            slippage += abs(exit_price - active_stop) * _quantity(plan, remaining)
            events.append(
                _event(
                    TradeLifecycleEventType.STOPPED_OUT,
                    observation.observed_at,
                    reason="active stop was touched",
                )
            )
            remaining = 0.0
            exit_reason = "stopped out"
            continue

        for index, target in enumerate(plan.targets):
            if target.label in targets_hit or not _target_touched(plan.direction, observation, target.price):
                continue
            targets_hit.add(target.label)
            close_pct = min(remaining, target.close_percentage)
            realized += _pnl(plan, entry_price, target.price, close_pct)
            fees += target.price * _quantity(plan, close_pct) * fee_rate
            remaining -= close_pct
            if remaining <= 1e-9:
                remaining = 0.0
                exit_price = target.price
                events.append(
                    _event(
                        TradeLifecycleEventType.FULL_TARGET_HIT,
                        observation.observed_at,
                        target_label=target.label,
                        reason=f"{target.label} closed the remaining position",
                    )
                )
                exit_reason = "full target hit"
                break
            events.append(
                _event(
                    TradeLifecycleEventType.PARTIAL_TARGET_HIT,
                    observation.observed_at,
                    target_label=target.label,
                    closed_percentage=100.0 - remaining,
                    reason=f"{target.label} partial target filled",
                )
            )
            if index == 0:
                active_stop = _breakeven_stop(plan, fee_rate, slippage_rate)
                events.append(
                    _event(
                        TradeLifecycleEventType.STOP_MOVED_TO_BREAKEVEN,
                        observation.observed_at,
                        stop_price=active_stop,
                        reason="first target confirmed; stop moved to cost-adjusted breakeven",
                    )
                )
            if index >= len(plan.targets) - 2 and not runner_active:
                runner_active = True
                events.append(
                    _event(
                        TradeLifecycleEventType.RUNNER_ACTIVATED,
                        observation.observed_at,
                        runner_active=True,
                        reason="remaining allocation promoted to runner",
                    )
                )
        if exit_reason is not None:
            continue

        if observation.fast_failure or observation.momentum_failed:
            exit_price = _exit_fill_price(plan.direction, observation.close, slippage_rate)
            realized += _pnl(plan, entry_price, exit_price, remaining)
            fees += exit_price * _quantity(plan, remaining) * fee_rate
            event_type = (
                TradeLifecycleEventType.EMERGENCY_STOP
                if observation.fast_failure
                else TradeLifecycleEventType.MOMENTUM_FAILURE_EXIT
            )
            events.append(_event(event_type, observation.observed_at, reason=event_type.value))
            remaining = 0.0
            exit_reason = "fast failure" if observation.fast_failure else "momentum failure"
            continue

        if runner_active:
            candidate = _trailing_stop(plan.direction, observation.close, trailing_distance_rate)
            active_stop = _tighten_stop(plan.direction, active_stop, candidate)
            events.append(
                _event(
                    TradeLifecycleEventType.TRAILING_STOP_UPDATED,
                    observation.observed_at,
                    trailing_stop_price=active_stop,
                    reason="runner trailing stop updated",
                )
            )

        if bars_open >= maximum_open_bars:
            exit_price = _exit_fill_price(plan.direction, observation.close, slippage_rate)
            realized += _pnl(plan, entry_price, exit_price, remaining)
            fees += exit_price * _quantity(plan, remaining) * fee_rate
            events.append(
                _event(
                    TradeLifecycleEventType.TIME_EXIT,
                    observation.observed_at,
                    reason="maximum open-bar limit reached",
                )
            )
            remaining = 0.0
            exit_reason = "time exit"

    lifecycle = replay_lifecycle_events(created_at=created_at, events=tuple(events))
    last_close = ordered[-1].close if ordered else plan.entry.ideal_entry
    unrealized = 0.0 if entry_price is None or remaining == 0.0 else _pnl(plan, entry_price, last_close, remaining)
    risk_amount = abs(plan.entry.ideal_entry - plan.initial_protection.stop_loss_price) * plan.initial_protection.quantity
    net_realized = realized - fees
    return TradeLifecycleExecution(
        lifecycle=lifecycle,
        entry_price=entry_price,
        exit_price=exit_price,
        remaining_percentage=remaining,
        realized_pnl=net_realized,
        unrealized_pnl=unrealized,
        total_fees=fees,
        total_slippage=slippage,
        realized_r_multiple=net_realized / risk_amount if risk_amount > 0.0 else 0.0,
        bars_pending=bars_pending,
        bars_open=bars_open,
        events=tuple(events),
        exit_reason=exit_reason,
    )


def _event(
    event_type: TradeLifecycleEventType,
    occurred_at: datetime,
    *,
    closed_percentage: float | None = None,
    stop_price: float | None = None,
    trailing_stop_price: float | None = None,
    target_label: str | None = None,
    runner_active: bool | None = None,
    reason: str | None = None,
) -> TradeLifecycleEvent:
    return TradeLifecycleEvent(
        event_type=event_type,
        occurred_at=occurred_at,
        closed_percentage=closed_percentage,
        stop_price=stop_price,
        trailing_stop_price=trailing_stop_price,
        target_label=target_label,
        runner_active=runner_active,
        reason=reason,
    )


def _entry_touched(plan: TradeManagementPlan, observation: LifecycleObservation) -> bool:
    return observation.low <= plan.entry.zone_high and observation.high >= plan.entry.zone_low


def _entry_fill_price(plan: TradeManagementPlan, slippage_rate: float) -> float:
    multiplier = 1.0 + slippage_rate if plan.direction is FuturesDirection.LONG else 1.0 - slippage_rate
    return plan.entry.ideal_entry * multiplier


def _exit_fill_price(direction: FuturesDirection, price: float, slippage_rate: float) -> float:
    multiplier = 1.0 - slippage_rate if direction is FuturesDirection.LONG else 1.0 + slippage_rate
    return price * multiplier


def _stop_touched(direction: FuturesDirection, observation: LifecycleObservation, stop: float) -> bool:
    return observation.low <= stop if direction is FuturesDirection.LONG else observation.high >= stop


def _target_touched(direction: FuturesDirection, observation: LifecycleObservation, target: float) -> bool:
    return observation.high >= target if direction is FuturesDirection.LONG else observation.low <= target


def _quantity(plan: TradeManagementPlan, percentage: float) -> float:
    return plan.initial_protection.quantity * percentage / 100.0


def _pnl(plan: TradeManagementPlan, entry: float, exit_price: float, percentage: float) -> float:
    movement = exit_price - entry if plan.direction is FuturesDirection.LONG else entry - exit_price
    return movement * _quantity(plan, percentage)


def _breakeven_stop(plan: TradeManagementPlan, fee_rate: float, slippage_rate: float) -> float:
    offset = plan.entry.ideal_entry * (fee_rate * 2.0 + slippage_rate)
    return plan.entry.ideal_entry + offset if plan.direction is FuturesDirection.LONG else plan.entry.ideal_entry - offset


def _trailing_stop(direction: FuturesDirection, close: float, distance_rate: float) -> float:
    return close * (1.0 - distance_rate) if direction is FuturesDirection.LONG else close * (1.0 + distance_rate)


def _tighten_stop(direction: FuturesDirection, current: float, candidate: float) -> float:
    return max(current, candidate) if direction is FuturesDirection.LONG else min(current, candidate)
