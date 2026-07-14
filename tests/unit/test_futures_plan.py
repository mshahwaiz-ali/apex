"""Tests for mapping approved setups into the futures output contract."""

from datetime import UTC, datetime
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
    current_price: float | None = None,
) -> SimpleNamespace:
    entry_price = current_price
    if entry_price is None:
        entry_price = 100.6 if inside_zone else 99.5
    entry = SimpleNamespace(
        lower=100.0,
        upper=101.0,
        preferred=100.5,
        current_price=entry_price,
        maximum_chase_price=101.5 if direction == "long" else 99.0,
        current_price_inside_zone=inside_zone,
    )
    stop_loss = SimpleNamespace(
        price=98.0 if direction == "long" else 103.0,
        quality_score=0.8,
        rationale=("structure invalidation",),
    )
    take_profits = (
        (
            SimpleNamespace(label="TP1", price=103.0, partial_close_pct=60.0),
            SimpleNamespace(label="TP2", price=106.0, partial_close_pct=40.0),
        )
        if direction == "long"
        else (
            SimpleNamespace(label="TP1", price=98.0, partial_close_pct=60.0),
            SimpleNamespace(label="TP2", price=95.0, partial_close_pct=40.0),
        )
    )
    return SimpleNamespace(
        decision_time=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
        direction=SimpleNamespace(value=direction),
        confidence_score=85.0,
        entry=entry,
        stop_loss=stop_loss,
        take_profits=take_profits,
        position_size=SimpleNamespace(
            required_leverage=2.0,
            notional_value=500.0,
            risk_amount=2.5,
        ),
        leverage=SimpleNamespace(liquidation_price_at_maximum=50.0),
    )


def _aggressive_account(
    *,
    wallet_balance: float = 200.0,
    leverage_mode: LeverageMode = LeverageMode.AUTOMATIC,
    manual_leverage: float | None = None,
    loss_percentage: float = 0.75,
) -> FuturesAccountInput:
    return FuturesAccountInput(
        wallet_balance=wallet_balance,
        leverage_mode=leverage_mode,
        manual_leverage=manual_leverage,
        risk_mode=RiskMode.AGGRESSIVE,
        maximum_account_loss_percentage=loss_percentage,
    )


def test_build_futures_plan_uses_risk_mode_preference_in_automatic_mode() -> None:
    plan = build_futures_plan(_setup(), _aggressive_account())

    assert plan["status"] == "APPROVED"
    assert plan["risk_mode"] == "AGGRESSIVE"
    assert plan["risk_mode_config"]["preferred_leverage"] == 5.0
    assert plan["entry"]["state"] == "READY_NOW"
    assert plan["entry_classification"]["state"] == "READY_NOW"
    assert plan["entry"]["classification_reasons"]
    assert plan["precision_entry"]["entry_state"] == "READY_NOW"
    assert plan["precision_entry"]["score"]["final_score"] > 0
    assert plan["position"]["leverage"] == 5.0
    assert plan["position"]["required_margin"] > 0
    assert plan["position"]["wallet_exposure_percentage"] <= 25.0
    assert plan["position"]["estimated_fees"] > 0
    assert plan["position"]["estimated_slippage"] > 0
    assert plan["position"]["total_maximum_planned_loss"] == pytest.approx(1.5)
    assert plan["targets"]["targets"][0]["close_percentage"] == 60.0
    assert plan["lifecycle"]["state"] == "GENERATED"

    management = plan["management_plan"]
    assert management["current_action"] == "ENTER"
    assert management["entry"]["action"] == "ENTER_NOW"
    assert management["entry"]["order_type"] == "MARKET"
    assert management["initial_protection"]["risk_percentage"] == 0.75
    assert management["initial_protection"]["risk_amount"] == pytest.approx(1.5)
    assert management["targets"][0]["cumulative_close_percentage"] == 60.0
    assert management["targets"][1]["cumulative_close_percentage"] == 100.0
    assert management["targets"][0]["expected_r_multiple"] > 0
    assert management["stop_management"][0]["action"] == "MOVE_STOP"
    assert management["emergency_exits"]


def test_build_futures_plan_preserves_safe_manual_leverage() -> None:
    account = _aggressive_account(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.MANUAL,
        manual_leverage=10.0,
    )

    plan = build_futures_plan(_setup(), account)

    assert plan["position"]["leverage"] == 10.0
    assert plan["position"]["required_margin"] > 0
    assert plan["position"]["wallet_exposure_percentage"] <= 25.0
    assert plan["position"]["leverage_selection_reason"] == (
        "manual leverage preserved after safety validation"
    )
    assert plan["management_plan"]["initial_protection"]["leverage"] == 10.0


def test_manual_leverage_above_profile_maximum_is_rejected() -> None:
    account = _aggressive_account(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.MANUAL,
        manual_leverage=11.0,
    )

    with pytest.raises(FuturesPlanSafetyError, match="exceeds AGGRESSIVE maximum"):
        build_futures_plan(_setup(), account)


def test_account_loss_override_above_mode_limit_is_rejected() -> None:
    account = _aggressive_account(loss_percentage=1.0)

    result = build_futures_plan_result(_setup(), account)

    assert result["status"] == "REJECTED"
    assert any("AGGRESSIVE mode limit 0.75%" in reason for reason in result["reasons"])


def test_modeled_planned_loss_is_sized_to_account_limit() -> None:
    result = build_futures_plan_result(_setup(), _aggressive_account())

    assert result["status"] == "APPROVED"
    assert result["position"]["total_maximum_planned_loss"] == pytest.approx(1.5)


def test_build_futures_plan_classifies_missed_long_entry() -> None:
    plan = build_futures_plan(
        _setup(inside_zone=False, current_price=101.6),
        _aggressive_account(),
    )

    assert plan["entry"]["state"] == "MISSED_ENTRY"
    assert plan["management_plan"]["current_action"] == "DO_NOT_ENTER"
    assert plan["management_plan"]["entry"]["order_type"] == "NONE"


def test_build_futures_plan_classifies_short_retest() -> None:
    plan = build_futures_plan(
        _setup(direction="short", inside_zone=False, current_price=99.5),
        _aggressive_account(),
    )

    assert plan["entry"]["state"] == "WAIT_FOR_RETEST"
    management = plan["management_plan"]
    assert management["current_action"] == "WAIT"
    assert management["entry"]["action"] == "WAIT_FOR_RETEST"
    assert management["targets"][0]["price"] == 98.0
    assert management["targets"][0]["expected_r_multiple"] > 0
    assert "at or above 103" in management["entry"]["cancellation_conditions"][0]
