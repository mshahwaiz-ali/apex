"""Map approved risk setups into the frozen futures output contract."""

from __future__ import annotations

from pathlib import Path

from apex.config import FuturesProductConfig, load_futures_product_config
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

DEFAULT_FUTURES_CONFIG_PATH = Path("config/futures.yaml")


class FuturesPlanSafetyError(ValueError):
    """Raised when a market setup is unsafe for the selected account profile."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def build_futures_plan(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    product_config: FuturesProductConfig | None = None,
) -> dict[str, object]:
    """Return a validated futures plan for an approved market setup."""

    config = product_config or load_futures_product_config(DEFAULT_FUTURES_CONFIG_PATH)
    defaults = config.defaults_for(account.risk_mode)
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
    planned_loss = setup.position_size.risk_amount

    reasons: list[str] = []
    if leverage > defaults.maximum_leverage:
        reasons.append(
            f"selected leverage {leverage:.2f}x exceeds "
            f"{account.risk_mode.value} maximum {defaults.maximum_leverage:.2f}x"
        )
    if account.manual_leverage is not None and leverage < defaults.minimum_leverage:
        reasons.append(
            f"manual leverage {leverage:.2f}x is below "
            f"{account.risk_mode.value} minimum {defaults.minimum_leverage:.2f}x"
        )
    if exposure_pct > defaults.maximum_wallet_exposure_percentage:
        reasons.append(
            f"wallet exposure {exposure_pct:.2f}% exceeds "
            f"{account.risk_mode.value} maximum "
            f"{defaults.maximum_wallet_exposure_percentage:.2f}%"
        )
    if planned_loss > account.maximum_account_loss_amount:
        reasons.append(
            f"planned loss {planned_loss:.2f} exceeds account limit "
            f"{account.maximum_account_loss_amount:.2f}"
        )
    if reasons:
        raise FuturesPlanSafetyError(tuple(reasons))

    position = PositionPlan(
        leverage=leverage,
        position_notional=setup.position_size.notional_value,
        required_margin=required_margin,
        wallet_exposure_percentage=exposure_pct,
        planned_loss_amount=planned_loss,
        estimated_fees=0.0,
        estimated_slippage=0.0,
        liquidation_price=setup.leverage.liquidation_price_at_maximum,
    )
    return {
        "status": "APPROVED",
        "entry": entry.model_dump(mode="json"),
        "stop": stop.model_dump(mode="json"),
        "targets": targets.model_dump(mode="json"),
        "position": position.model_dump(mode="json"),
    }


def build_futures_plan_result(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    product_config: FuturesProductConfig | None = None,
) -> dict[str, object]:
    """Return an approved or rejected futures-plan payload without hiding analysis."""

    try:
        return build_futures_plan(setup, account, product_config=product_config)
    except FuturesPlanSafetyError as exc:
        return {
            "status": "REJECTED",
            "reasons": list(exc.reasons),
        }
