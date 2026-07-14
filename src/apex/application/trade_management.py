"""Compose canonical manual trade-management instructions for futures plans."""

from __future__ import annotations

from datetime import datetime, timedelta

from apex.domain import (
    CurrentAction,
    EmergencyExitRule,
    EntryInstruction,
    EntryInstructionAction,
    EntryPlan,
    FuturesAccountInput,
    FuturesDirection,
    InitialProtectionInstruction,
    ManagementTarget,
    ManagementTriggerType,
    PositionPlan,
    RecommendedOrderType,
    StopInstructionType,
    StopManagementRule,
    TargetPlan,
    TradeManagementPlan,
    entry_action_for_state,
)

DEFAULT_ENTRY_VALIDITY = timedelta(minutes=15)


def build_trade_management_plan(
    *,
    direction: FuturesDirection,
    entry: EntryPlan,
    position: PositionPlan,
    targets: TargetPlan,
    account: FuturesAccountInput,
    generated_at: datetime | None = None,
    entry_validity: timedelta = DEFAULT_ENTRY_VALIDITY,
) -> TradeManagementPlan:
    """Build complete, deterministic manual instructions from an approved plan."""

    if generated_at is not None and (
        generated_at.tzinfo is None or generated_at.utcoffset() is None
    ):
        raise ValueError("trade-management generation time must be timezone-aware")
    if entry_validity <= timedelta(0):
        raise ValueError("entry validity must be positive")

    entry_action, current_action = entry_action_for_state(entry.state)
    order_type = _order_type_for_action(entry_action)
    expires_at = (
        None
        if generated_at is None or entry_action is EntryInstructionAction.REJECT
        else generated_at + entry_validity
    )
    entry_instruction = EntryInstruction(
        action=entry_action,
        entry_state=entry.state,
        zone_low=entry.zone_low,
        zone_high=entry.zone_high,
        ideal_entry=entry.ideal_entry,
        maximum_chase_price=entry.maximum_chase_price,
        order_type=order_type,
        expires_at=expires_at,
        cancellation_conditions=(
            _invalidation_condition(direction, position.structural_stop),
            "cancel if price moves beyond the configured maximum chase price before entry",
            "cancel automatically when the timezone-aware entry expiry is reached",
            "cancel if the setup lifecycle becomes invalidated or account-locked",
        ),
    )
    protection = InitialProtectionInstruction(
        stop_loss_price=_required_stop(position),
        stop_type=StopInstructionType.STOP_MARKET,
        risk_percentage=account.maximum_account_loss_percentage,
        risk_amount=position.total_maximum_planned_loss,
        quantity=position.position_quantity,
        notional=position.position_notional,
        margin=position.required_margin,
        leverage=position.leverage,
        estimated_fees=position.estimated_fees,
        estimated_slippage=position.estimated_slippage,
        estimated_liquidation_price=position.liquidation_price,
        stop_to_liquidation_buffer=position.stop_to_liquidation_price_buffer,
    )
    management_targets = _management_targets(
        direction=direction,
        entry_price=entry.ideal_entry,
        stop_price=protection.stop_loss_price,
        targets=targets,
    )
    stop_management = _stop_management_rules(
        targets=management_targets,
        breakeven_price=entry.ideal_entry,
    )
    emergency_exits = (
        EmergencyExitRule(
            trigger_type=ManagementTriggerType.STRUCTURAL_BREAK,
            condition=_emergency_structure_condition(direction, protection.stop_loss_price),
        ),
        EmergencyExitRule(
            trigger_type=ManagementTriggerType.SPREAD_EXPANSION,
            condition="close the trade if executable spread expands beyond configured safety limits",
        ),
        EmergencyExitRule(
            trigger_type=ManagementTriggerType.ACCOUNT_LOCKOUT,
            condition="close or cancel according to the active account-policy lockout instruction",
        ),
    )
    return TradeManagementPlan(
        direction=direction,
        entry=entry_instruction,
        initial_protection=protection,
        targets=management_targets,
        stop_management=stop_management,
        emergency_exits=emergency_exits,
        current_action=current_action,
    )


def _order_type_for_action(action: EntryInstructionAction) -> RecommendedOrderType:
    if action is EntryInstructionAction.ENTER_NOW:
        return RecommendedOrderType.MARKET
    if action is EntryInstructionAction.PLACE_LIMIT:
        return RecommendedOrderType.LIMIT
    if action in {
        EntryInstructionAction.WAIT_FOR_RETEST,
        EntryInstructionAction.WAIT_FOR_RECLAIM,
        EntryInstructionAction.WATCH,
    }:
        return RecommendedOrderType.STOP_LIMIT
    return RecommendedOrderType.NONE


def _required_stop(position: PositionPlan) -> float:
    if position.structural_stop is None:
        raise ValueError("trade management requires a structural stop")
    return position.structural_stop


def _management_targets(
    *,
    direction: FuturesDirection,
    entry_price: float,
    stop_price: float,
    targets: TargetPlan,
) -> tuple[ManagementTarget, ...]:
    risk_distance = abs(entry_price - stop_price)
    if risk_distance <= 0.0:
        raise ValueError("trade management requires positive entry-to-stop distance")
    cumulative = 0.0
    result: list[ManagementTarget] = []
    for target in targets.targets:
        cumulative += target.close_percentage
        reward_distance = (
            target.price - entry_price
            if direction is FuturesDirection.LONG
            else entry_price - target.price
        )
        if reward_distance <= 0.0:
            raise ValueError("management targets must provide positive directional reward")
        result.append(
            ManagementTarget(
                label=target.label,
                price=target.price,
                close_percentage=target.close_percentage,
                cumulative_close_percentage=cumulative,
                expected_r_multiple=reward_distance / risk_distance,
                rationale=f"approved {target.label} target from the validated risk setup",
            )
        )
    return tuple(result)


def _stop_management_rules(
    *,
    targets: tuple[ManagementTarget, ...],
    breakeven_price: float,
) -> tuple[StopManagementRule, ...]:
    first_target = targets[0]
    rules = [
        StopManagementRule(
            trigger_type=ManagementTriggerType.TARGET_FILLED,
            trigger_reference=first_target.label,
            action=CurrentAction.MOVE_STOP,
            stop_price=breakeven_price,
            instruction=(
                f"after {first_target.label} is confirmed, move the active stop to the "
                "validated entry price; do not tighten it before that trigger"
            ),
        )
    ]
    if len(targets) > 1:
        rules.append(
            StopManagementRule(
                trigger_type=ManagementTriggerType.TARGET_FILLED,
                trigger_reference=targets[-1].label,
                action=CurrentAction.HOLD,
                instruction="allow the final allocated target to complete under the active stop",
            )
        )
    return tuple(rules)


def _invalidation_condition(
    direction: FuturesDirection,
    structural_stop: float | None,
) -> str:
    stop_text = "the structural stop" if structural_stop is None else f"{structural_stop:g}"
    relation = "at or below" if direction is FuturesDirection.LONG else "at or above"
    return f"cancel before entry if price trades {relation} {stop_text}"


def _emergency_structure_condition(
    direction: FuturesDirection,
    stop_price: float,
) -> str:
    relation = "below" if direction is FuturesDirection.LONG else "above"
    return f"close all if market structure confirms invalidation {relation} {stop_price:g}"
