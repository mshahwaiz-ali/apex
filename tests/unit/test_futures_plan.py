"""Tests for mapping approved setups into the futures output contract."""

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from apex.application import (
    FuturesPlanSafetyError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.domain import FuturesAccountInput, LeverageMode, RiskMode
from apex.risk import RiskApprovedSetup


def _setup(
    *,
    direction: str = "long",
    inside_zone: bool = True,
    current_price: float | None = None,
) -> RiskApprovedSetup:
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
    return cast(
        RiskApprovedSetup,
        SimpleNamespace(
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
        ),
    )


def _mapping(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    return value


def _strings(value: object) -> list[str]:
    assert isinstance(value, list)
    assert all(isinstance(item, str) for item in value)
    return cast(list[str], value)


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
    risk_mode_config = _mapping(plan["risk_mode_config"])
    entry = _mapping(plan["entry"])
    entry_classification = _mapping(plan["entry_classification"])
    precision_entry = _mapping(plan["precision_entry"])
    precision_score = _mapping(precision_entry["score"])
    position = _mapping(plan["position"])
    targets = _mapping(plan["targets"])
    target_rows = cast(list[dict[str, object]], targets["targets"])
    lifecycle = _mapping(plan["lifecycle"])
    management = _mapping(plan["management_plan"])
    management_entry = _mapping(management["entry"])
    initial_protection = _mapping(management["initial_protection"])
    management_targets = cast(list[dict[str, object]], management["targets"])
    stop_management = cast(list[dict[str, object]], management["stop_management"])

    assert plan["status"] == "APPROVED"
    assert plan["risk_mode"] == "AGGRESSIVE"
    assert risk_mode_config["preferred_leverage"] == 5.0
    assert entry["state"] == "READY_NOW"
    assert entry_classification["state"] == "READY_NOW"
    assert entry["classification_reasons"]
    assert precision_entry["entry_state"] == "READY_NOW"
    assert cast(float, precision_score["final_score"]) > 0
    assert position["leverage"] == 5.0
    assert cast(float, position["required_margin"]) > 0
    assert cast(float, position["wallet_exposure_percentage"]) <= 25.0
    assert cast(float, position["estimated_fees"]) > 0
    assert cast(float, position["estimated_slippage"]) > 0
    assert position["total_maximum_planned_loss"] == pytest.approx(1.5)
    assert target_rows[0]["close_percentage"] == 60.0
    assert lifecycle["state"] == "GENERATED"

    assert management["current_action"] == "ENTER"
    assert management_entry["action"] == "ENTER_NOW"
    assert management_entry["order_type"] == "MARKET"
    assert initial_protection["risk_percentage"] == 0.75
    assert initial_protection["risk_amount"] == pytest.approx(1.5)
    assert management_targets[0]["cumulative_close_percentage"] == 60.0
    assert management_targets[1]["cumulative_close_percentage"] == 100.0
    assert cast(float, management_targets[0]["expected_r_multiple"]) > 0
    assert stop_management[0]["action"] == "MOVE_STOP"
    assert management["emergency_exits"]


def test_build_futures_plan_preserves_safe_manual_leverage() -> None:
    account = _aggressive_account(
        wallet_balance=100.0,
        leverage_mode=LeverageMode.MANUAL,
        manual_leverage=10.0,
    )

    plan = build_futures_plan(_setup(), account)
    position = _mapping(plan["position"])
    management = _mapping(plan["management_plan"])
    initial_protection = _mapping(management["initial_protection"])

    assert position["leverage"] == 10.0
    assert cast(float, position["required_margin"]) > 0
    assert cast(float, position["wallet_exposure_percentage"]) <= 25.0
    assert position["leverage_selection_reason"] == (
        "manual leverage preserved after safety validation"
    )
    assert initial_protection["leverage"] == 10.0


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
    assert any("AGGRESSIVE mode limit 0.75%" in reason for reason in _strings(result["reasons"]))


def test_modeled_planned_loss_is_sized_to_account_limit() -> None:
    result = build_futures_plan_result(_setup(), _aggressive_account())
    position = _mapping(result["position"])

    assert result["status"] == "APPROVED"
    assert position["total_maximum_planned_loss"] == pytest.approx(1.5)


def test_build_futures_plan_classifies_missed_long_entry() -> None:
    plan = build_futures_plan(
        _setup(inside_zone=False, current_price=101.6),
        _aggressive_account(),
    )
    entry = _mapping(plan["entry"])
    management = _mapping(plan["management_plan"])
    management_entry = _mapping(management["entry"])

    assert entry["state"] == "MISSED_ENTRY"
    assert management["current_action"] == "DO_NOT_ENTER"
    assert management_entry["order_type"] == "NONE"


def test_build_futures_plan_classifies_short_retest() -> None:
    plan = build_futures_plan(
        _setup(direction="short", inside_zone=False, current_price=99.5),
        _aggressive_account(),
    )
    entry = _mapping(plan["entry"])
    management = _mapping(plan["management_plan"])
    management_entry = _mapping(management["entry"])
    management_targets = cast(list[dict[str, object]], management["targets"])
    cancellation_conditions = cast(list[str], management_entry["cancellation_conditions"])

    assert entry["state"] == "WAIT_FOR_RETEST"
    assert management["current_action"] == "WAIT"
    assert management_entry["action"] == "WAIT_FOR_RETEST"
    assert management_targets[0]["price"] == 98.0
    assert cast(float, management_targets[0]["expected_r_multiple"]) > 0
    assert "at or above 103" in cancellation_conditions[0]
