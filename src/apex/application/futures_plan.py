"""Map approved risk setups into the frozen futures output contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apex.application.precision_entry import build_precision_entry_plan
from apex.config import FuturesProductConfig, load_futures_product_config
from apex.domain import (
    EntryClassificationInput,
    EntryPlan,
    FuturesAccountInput,
    FuturesDirection,
    LeverageMode,
    PositionPlan,
    StopPlan,
    TargetLeg,
    TargetPlan,
    TradeLifecycle,
    classify_entry_state,
)
from apex.risk.contracts import RiskApprovedSetup

DEFAULT_FUTURES_CONFIG_PATH = Path("config/futures.yaml")


class FuturesPlanSafetyError(ValueError):
    """Raised when a market setup is unsafe for the selected account profile."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass(frozen=True, slots=True)
class _ModeledPosition:
    quantity: float
    notional: float
    gross_structural_risk: float
    entry_fee: float
    exit_fee: float
    entry_slippage: float
    exit_slippage: float
    total_loss: float

    @property
    def estimated_fees(self) -> float:
        return self.entry_fee + self.exit_fee

    @property
    def estimated_slippage(self) -> float:
        return self.entry_slippage + self.exit_slippage


@dataclass(frozen=True, slots=True)
class _LeverageSelection:
    leverage: float
    liquidation_price: float
    buffer_price: float
    buffer_percentage: float
    reason: str
    limiting_constraint: str


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
    classification = classify_entry_state(
        EntryClassificationInput(
            direction=direction,
            current_price=setup.entry.current_price,
            zone_low=setup.entry.lower,
            zone_high=setup.entry.upper,
            ideal_entry=setup.entry.preferred,
            maximum_chase_price=setup.entry.maximum_chase_price,
            structural_invalidation=setup.stop_loss.price,
        )
    )
    precision_entry = build_precision_entry_plan(setup)
    entry = EntryPlan(
        direction=direction,
        state=classification.state,
        current_price=setup.entry.current_price,
        zone_low=setup.entry.lower,
        zone_high=setup.entry.upper,
        ideal_entry=setup.entry.preferred,
        maximum_chase_price=setup.entry.maximum_chase_price,
        classification_reasons=classification.reasons,
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
        else defaults.preferred_leverage
    )
    modeled_position = _model_position(
        setup=setup,
        account=account,
        product_config=config,
    )
    leverage_selection = _select_leverage(
        setup=setup,
        account=account,
        product_config=config,
        position=modeled_position,
        requested_leverage=leverage,
    )
    required_margin = modeled_position.notional / leverage_selection.leverage
    exposure_pct = (required_margin / account.wallet_balance) * 100
    planned_loss = modeled_position.total_loss

    reasons: list[str] = []
    if planned_loss > account.maximum_account_loss_amount:
        reasons.append(
            f"planned loss {planned_loss:.2f} exceeds account limit "
            f"{account.maximum_account_loss_amount:.2f}"
        )
    if reasons:
        raise FuturesPlanSafetyError(tuple(reasons))

    position = PositionPlan(
        leverage=leverage_selection.leverage,
        leverage_mode=account.leverage_mode,
        position_quantity=modeled_position.quantity,
        position_notional=modeled_position.notional,
        required_margin=required_margin,
        wallet_exposure_percentage=exposure_pct,
        planned_loss_amount=planned_loss,
        gross_structural_movement_risk=modeled_position.gross_structural_risk,
        entry_fee_allowance=modeled_position.entry_fee,
        exit_fee_allowance=modeled_position.exit_fee,
        entry_slippage_allowance=modeled_position.entry_slippage,
        exit_slippage_allowance=modeled_position.exit_slippage,
        estimated_fees=modeled_position.estimated_fees,
        estimated_slippage=modeled_position.estimated_slippage,
        total_maximum_planned_loss=modeled_position.total_loss,
        liquidation_price=leverage_selection.liquidation_price,
        structural_stop=setup.stop_loss.price,
        emergency_invalidation=setup.stop_loss.price,
        stop_to_liquidation_price_buffer=leverage_selection.buffer_price,
        stop_to_liquidation_percentage_buffer=leverage_selection.buffer_percentage,
        leverage_selection_reason=leverage_selection.reason,
        limiting_constraint=leverage_selection.limiting_constraint,
        warnings=("liquidation price is a generic isolated-margin estimate, not exchange-exact",),
    )
    lifecycle = TradeLifecycle(
        created_at=setup.decision_time,
        updated_at=setup.decision_time,
    )
    return {
        "status": "APPROVED",
        "entry": entry.model_dump(mode="json"),
        "entry_classification": classification.model_dump(mode="json"),
        "precision_entry": precision_entry.model_dump(mode="json"),
        "stop": stop.model_dump(mode="json"),
        "targets": targets.model_dump(mode="json"),
        "position": position.model_dump(mode="json"),
        "lifecycle": lifecycle.model_dump(mode="json"),
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


def _model_position(
    *,
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    product_config: FuturesProductConfig,
) -> _ModeledPosition:
    entry_price = setup.entry.preferred
    stop_distance = abs(entry_price - setup.stop_loss.price)
    if stop_distance <= 0.0:
        raise FuturesPlanSafetyError(("stop distance must be greater than zero",))
    movement_fraction = stop_distance / entry_price
    cost_fraction = product_config.execution_costs.total_cost_fraction
    total_loss_fraction = movement_fraction + cost_fraction
    if total_loss_fraction <= 0.0:
        raise FuturesPlanSafetyError(("modeled loss fraction must be greater than zero",))

    notional = account.maximum_account_loss_amount / total_loss_fraction
    quantity = notional / entry_price
    gross_risk = notional * movement_fraction
    entry_fee = notional * product_config.execution_costs.entry_fee_percentage / 100.0
    exit_fee = notional * product_config.execution_costs.exit_fee_percentage / 100.0
    entry_slippage = notional * product_config.execution_costs.entry_slippage_percentage / 100.0
    exit_slippage = notional * product_config.execution_costs.exit_slippage_percentage / 100.0
    total_loss = gross_risk + entry_fee + exit_fee + entry_slippage + exit_slippage
    return _ModeledPosition(
        quantity=quantity,
        notional=notional,
        gross_structural_risk=gross_risk,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        entry_slippage=entry_slippage,
        exit_slippage=exit_slippage,
        total_loss=total_loss,
    )


def _select_leverage(
    *,
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    product_config: FuturesProductConfig,
    position: _ModeledPosition,
    requested_leverage: float,
) -> _LeverageSelection:
    defaults = product_config.defaults_for(account.risk_mode)
    if account.leverage_mode is LeverageMode.MANUAL:
        if requested_leverage < defaults.minimum_leverage:
            raise FuturesPlanSafetyError(
                (
                    f"manual leverage {requested_leverage:.2f}x is below "
                    f"{account.risk_mode.value} minimum {defaults.minimum_leverage:.2f}x",
                )
            )
        if requested_leverage > defaults.maximum_leverage:
            raise FuturesPlanSafetyError(
                (
                    f"manual leverage {requested_leverage:.2f}x exceeds "
                    f"{account.risk_mode.value} maximum {defaults.maximum_leverage:.2f}x",
                )
            )
        selected = _evaluate_leverage(
            setup=setup,
            account=account,
            product_config=product_config,
            position=position,
            leverage=requested_leverage,
        )
        if selected is None:
            raise FuturesPlanSafetyError(
                (
                    f"manual leverage {requested_leverage:.2f}x violates wallet exposure "
                    "or liquidation safety",
                )
            )
        return selected

    failures: list[str] = []
    for candidate in _automatic_leverage_candidates(
        minimum=defaults.minimum_leverage,
        preferred=defaults.preferred_leverage,
        maximum=defaults.maximum_leverage,
    ):
        selected = _evaluate_leverage(
            setup=setup,
            account=account,
            product_config=product_config,
            position=position,
            leverage=candidate,
        )
        if selected is not None:
            return selected
        failures.append(f"{candidate:.2f}x")
    raise FuturesPlanSafetyError(
        (
            "no valid automatic leverage satisfies wallet exposure and liquidation safety",
            f"evaluated leverage candidates: {', '.join(failures)}",
        )
    )


def _automatic_leverage_candidates(
    *,
    minimum: float,
    preferred: float,
    maximum: float,
) -> tuple[float, ...]:
    rounded_minimum = int(minimum)
    rounded_maximum = int(maximum)
    values = {minimum, preferred, maximum}
    values.update(float(value) for value in range(rounded_minimum, rounded_maximum + 1))
    valid = tuple(value for value in values if minimum <= value <= maximum)
    return tuple(sorted(valid, key=lambda value: (abs(value - preferred), value)))


def _evaluate_leverage(
    *,
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    product_config: FuturesProductConfig,
    position: _ModeledPosition,
    leverage: float,
) -> _LeverageSelection | None:
    defaults = product_config.defaults_for(account.risk_mode)
    if leverage < defaults.minimum_leverage or leverage > defaults.maximum_leverage:
        return None
    required_margin = position.notional / leverage
    exposure_pct = required_margin / account.wallet_balance * 100.0
    if exposure_pct > defaults.maximum_wallet_exposure_percentage:
        return None

    liquidation = _estimate_liquidation(
        setup=setup,
        product_config=product_config,
        leverage=leverage,
    )
    if liquidation is None:
        return None
    liquidation_price, buffer_price, buffer_pct = liquidation
    if buffer_pct < product_config.execution_costs.minimum_stop_to_liquidation_buffer_percentage:
        return None
    reason = (
        "manual leverage preserved after safety validation"
        if account.leverage_mode is LeverageMode.MANUAL
        else "selected closest valid leverage to risk-mode preference"
    )
    return _LeverageSelection(
        leverage=leverage,
        liquidation_price=liquidation_price,
        buffer_price=buffer_price,
        buffer_percentage=buffer_pct,
        reason=reason,
        limiting_constraint="wallet_exposure_and_liquidation_buffer",
    )


def _estimate_liquidation(
    *,
    setup: RiskApprovedSetup,
    product_config: FuturesProductConfig,
    leverage: float,
) -> tuple[float, float, float] | None:
    entry_price = setup.entry.preferred
    maintenance_fraction = product_config.execution_costs.maintenance_margin_percentage / 100.0
    liquidation_buffer_fraction = (
        product_config.execution_costs.liquidation_fee_buffer_percentage / 100.0
    )
    liquidation_distance_fraction = (
        1.0 / leverage - maintenance_fraction - liquidation_buffer_fraction
    )
    if liquidation_distance_fraction <= 0.0:
        return None
    direction = FuturesDirection(setup.direction.value.upper())
    if direction is FuturesDirection.LONG:
        liquidation_price = entry_price * (1.0 - liquidation_distance_fraction)
        buffer_price = setup.stop_loss.price - liquidation_price
    else:
        liquidation_price = entry_price * (1.0 + liquidation_distance_fraction)
        buffer_price = liquidation_price - setup.stop_loss.price
    if buffer_price <= 0.0:
        return None
    return liquidation_price, buffer_price, buffer_price / entry_price * 100.0
