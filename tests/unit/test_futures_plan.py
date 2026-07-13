"""Tests for mapping approved setups into the futures output contract."""

from types import SimpleNamespace

import pytest

from apex.application import (
    FuturesPlanSafetyError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.domain import FuturesAccountInput, LeverageMode, RiskMode


def _setup(
    *,
    direction: str = "long",
    inside_zone: bool = True,
    required_leverage: float = 10.0,
    notional_value: float = 500.0,
    risk_amount: float = 10.0,
) -> SimpleNamespace:
    entry = SimpleNamespace(
        lower=100.0,
        upper=101.0,
        preferred=100.5,
        current_price=100.6 if inside_zone else 99.5,
        maximum_chase_price=101.5 if direction == "long" else 99.0,
        current_price_inside_zone=inside_zone,
    )
    stop_loss = SimpleNamespace(price=98.0, rationale=("structure invalidation",))
    take_profits = (
        SimpleNamespace(label="TP1", price=103.0, partial_close_pct=60.0),
        SimpleNamespace(label="TP2", price=106.0, partial_close_pct=40.0),
    )
    position_size = SimpleNamespace(
        required_leverage=required_leverage,
        notional_value=notional_value,
        risk_amount=risk_amount,
    )
    leverage = SimpleNamespace(liquidation_price_at_maximum=95.0)
    return SimpleNamespace(
        direction=SimpleNamespace(value=direction),
        entry=entry,
        stop_loss=stop_loss,
        take_profits=take_profits,
        position_size=position_size,
        leverage=leverage,
    )


def test_build_futures_plan_uses_setup_leverage_in_automatic_mode() -> None:
    account = FuturesAccountInput(
        wallet_balance=200.0,
        leverage_mode=LeverageMode.AUTOMATIC,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=10.0,
    )

    plan = build_futures_plan(_setup(), account)

    assert plan["status"] == "APPROVED"
    assert plan["entry"]["state"] == "READY_NOW"
    assert plan["position"]["leverage"] == 10.0
    assert plan["position"]["required_margin"] == 50.0
    assert plan["position"]["wallet_exposure_percentage"] == 25.0
    assert plan["targets"]["targets"][0]["close_percentage"] == 60.0


def test_build_futures_plan_uses_manual_leverage() -> None:
    account = FuturesAccountInput(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.MANUAL,
        manual_leverage=20.0,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=10.0,
    )

    plan = build_futures_plan(_setup(), account)

    assert plan["position"]["leverage"] == 20.0
    assert plan["position"]["required_margin"] == 25.0
    assert plan["position"]["wallet_exposure_percentage"] == 25.0


def test_manual_leverage_above_profile_maximum_is_rejected() -> None:
    account = FuturesAccountInput(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.MANUAL,
        manual_leverage=25.0,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=10.0,
    )

    with pytest.raises(FuturesPlanSafetyError, match="exceeds AGGRESSIVE maximum"):
        build_futures_plan(_setup(), account)


def test_wallet_exposure_above_profile_limit_is_rejected() -> None:
    account = FuturesAccountInput(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.AUTOMATIC,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=20.0,
    )

    result = build_futures_plan_result(_setup(), account)

    assert result["status"] == "REJECTED"
    assert any("wallet exposure" in reason for reason in result["reasons"])


def test_planned_loss_above_account_limit_is_rejected() -> None:
    account = FuturesAccountInput(
        wallet_balance=200.0,
        leverage_mode=LeverageMode.AUTOMATIC,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=2.5,
    )

    result = build_futures_plan_result(_setup(risk_amount=10.0), account)

    assert result["status"] == "REJECTED"
    assert any("planned loss" in reason for reason in result["reasons"])
