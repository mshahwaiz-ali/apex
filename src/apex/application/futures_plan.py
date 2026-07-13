"""Map approved risk setups into the frozen futures output contract."""

from __future__ import annotations

from apex.domain import (
    EntryPlan,
    EntryState,
    FuturesAccountInput,
    FuturesDirection,
    PositionPlan,
    StopPlan,
    TargetLeg,
    TargetPlan,
)
from apex.risk.contracts import RiskApprovedSetup


def build_futures_plan(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
) -> dict[str, object]:
    """Return a non-breaking futures-plan payload for an approved setup."""

    direction = FuturesDirection(setup.direction.value.upper())
    state = (
        EntryState.READY_NOW
        if setup.entry.current_price_inside_zone
        else EntryState.APPROACHING_ENTRY
    )
    entry = EntryPlan(
        direction=direction,
        state=state,
        current_price=setup.entry.current_price,
        zone_low=setup.entry.lower,
        zone_high=setup.entry.upper,
        ideal_entry=setup.entry.preferred,
        maximum_chase_price=setup.entry.maximum_chase_price,
    )
    rationale = "; ".join(setup.stop_loss.rationale)
    stop = StopPlan(
        soft_failure=setup.stop_loss.price,
        structural_stop=setup.stop_loss.price,
        emergency_stop=setup.stop_loss.price,
        rationale=rationale,
    )
    targets = TargetPlan(
        targets=tuple(
            TargetLeg(
                label=target.label,
                price=target.price,
                close_percentage=target.partial_close_pct,
            )
            for target in setup.take_profits
        )
    )
    leverage = (
        account.manual_leverage
        if account.manual_leverage is not None
        else setup.position_size.required_leverage
    )
    required_margin = setup.position_size.notional_value / leverage
    exposure_pct = (required_margin / account.wallet_balance) * 100
    position = PositionPlan(
        leverage=leverage,
        position_notional=setup.position_size.notional_value,
        required_margin=required_margin,
        wallet_exposure_percentage=exposure_pct,
        planned_loss_amount=setup.position_size.risk_amount,
        estimated_fees=0.0,
        estimated_slippage=0.0,
        liquidation_price=setup.leverage.liquidation_price_at_maximum,
    )
    return {
        "entry": entry.model_dump(mode="json"),
        "stop": stop.model_dump(mode="json"),
        "targets": targets.model_dump(mode="json"),
        "position": position.model_dump(mode="json"),
    }
