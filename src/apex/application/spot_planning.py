"""Deterministic S4 spot entry, allocation, exit, and lifecycle planning."""

from __future__ import annotations

from dataclasses import dataclass

from apex.config.spot import SpotProductConfig
from apex.domain.spot import (
    SpotAccountInput,
    SpotEntryLeg,
    SpotEntryPlan,
    SpotEntryState,
    SpotLifecycleSnapshot,
    SpotLifecycleState,
    SpotPositionPlan,
    SpotStopPlan,
    SpotTargetLeg,
    SpotTargetPlan,
)
from apex.domain.spot_strategy import SpotStrategyCandidate, SpotStrategyDecision


@dataclass(frozen=True)
class SpotPlanningRequest:
    candidate: SpotStrategyCandidate
    account: SpotAccountInput
    current_price: float
    support_price: float
    resistance_price: float
    deeper_support_price: float
    recovery_entry_price: float
    correlated_sector_exposure: float = 0.0


@dataclass(frozen=True)
class SpotPlanningResult:
    entry_plan: SpotEntryPlan
    stop_plan: SpotStopPlan
    position_plan: SpotPositionPlan
    target_plan: SpotTargetPlan
    lifecycle: SpotLifecycleSnapshot


def build_spot_plan(
    request: SpotPlanningRequest,
    *,
    config: SpotProductConfig,
) -> SpotPlanningResult:
    """Build a bounded cash-funded spot plan from an approved S3 candidate."""

    if request.candidate.decision is not SpotStrategyDecision.APPROVE:
        raise ValueError("spot planning requires an approved strategy candidate")
    if request.account.open_position_count >= config.allocation.maximum_open_positions:
        raise ValueError("maximum open spot positions reached")
    if not 0 <= request.correlated_sector_exposure <= request.account.total_spot_equity:
        raise ValueError("correlated-sector exposure must be within account equity")

    invalidation = request.candidate.invalidation_price
    if not invalidation < min(
        request.current_price,
        request.support_price,
        request.deeper_support_price,
        request.recovery_entry_price,
    ):
        raise ValueError("spot invalidation must remain below all planned entries")

    allocations = config.entry.default_entry_allocations
    prices = (
        request.current_price,
        request.deeper_support_price,
        request.recovery_entry_price,
    )[: len(allocations)]
    entries = tuple(
        SpotEntryLeg(
            label=f"ENTRY_{index + 1}",
            price=price,
            allocation_percentage=allocation,
            requires_confirmation=index == len(prices) - 1 and index > 0,
        )
        for index, (price, allocation) in enumerate(zip(prices, allocations, strict=True))
    )
    maximum_chase = request.current_price * (
        1 + config.entry.maximum_chase_percentage / 100
    )
    entry_plan = SpotEntryPlan(
        state=SpotEntryState.READY_NOW,
        current_price=request.current_price,
        entries=entries,
        maximum_chase_price=maximum_chase,
        invalidation_price=invalidation,
    )

    average_entry = sum(
        leg.price * leg.allocation_percentage / 100 for leg in entry_plan.entries
    )
    risk_per_unit = average_entry - invalidation
    if risk_per_unit <= 0:
        raise ValueError("spot risk per unit must be positive")

    equity = request.account.total_spot_equity
    allowed_loss = equity * config.allocation.maximum_account_loss_percentage / 100
    capital_by_risk = allowed_loss * average_entry / risk_per_unit
    capital_by_position = (
        equity * config.allocation.maximum_allocation_per_position_percentage / 100
    )
    remaining_total_exposure = max(
        0.0,
        equity * config.allocation.maximum_total_spot_exposure_percentage / 100
        - request.account.current_spot_exposure,
    )
    remaining_sector_exposure = max(
        0.0,
        equity
        * config.allocation.maximum_correlated_sector_exposure_percentage
        / 100
        - request.correlated_sector_exposure,
    )
    reserve_floor = equity * config.allocation.minimum_quote_reserve_percentage / 100
    cash_after_reserve = max(0.0, request.account.available_quote_balance - reserve_floor)
    capital = min(
        capital_by_risk,
        capital_by_position,
        remaining_total_exposure,
        remaining_sector_exposure,
        cash_after_reserve,
    )
    if capital <= 0:
        raise ValueError("spot allocation limits leave no capital available")

    quantity = capital / average_entry
    planned_loss = quantity * risk_per_unit
    position_plan = SpotPositionPlan(
        average_entry_price=average_entry,
        quantity=quantity,
        capital_allocated=capital,
        allocation_percentage_of_equity=capital / equity * 100,
        planned_loss_amount=planned_loss,
        planned_loss_percentage_of_equity=planned_loss / equity * 100,
        remaining_quote_reserve=request.account.available_quote_balance - capital,
    )

    stop_plan = SpotStopPlan(
        structural_invalidation_price=invalidation,
        protective_stop_price=invalidation,
        thesis_failure_reason="approved spot thesis invalidated below structural support",
        market_regime_exit_required=True,
    )

    risk_distance = average_entry - invalidation
    target_prices = (
        max(request.resistance_price, average_entry + risk_distance),
        average_entry + risk_distance * 2,
        average_entry + risk_distance * 3,
        average_entry + risk_distance * 4,
    )[: len(config.exit.default_target_allocations)]
    target_plan = SpotTargetPlan(
        targets=tuple(
            SpotTargetLeg(
                label="RUNNER" if index == len(target_prices) - 1 else f"TP{index + 1}",
                price=price,
                sell_percentage=allocation,
                rationale=(
                    "higher-timeframe trailing runner"
                    if index == len(target_prices) - 1
                    else f"realize profit near {index + 1}R"
                ),
            )
            for index, (price, allocation) in enumerate(
                zip(target_prices, config.exit.default_target_allocations, strict=True)
            )
        )
    )

    lifecycle = SpotLifecycleSnapshot(
        state=SpotLifecycleState.WAITING_FOR_ENTRY,
        active_stop_price=stop_plan.protective_stop_price,
    )
    return SpotPlanningResult(
        entry_plan=entry_plan,
        stop_plan=stop_plan,
        position_plan=position_plan,
        target_plan=target_plan,
        lifecycle=lifecycle,
    )
