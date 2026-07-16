"""Tests for the frozen futures product contract."""

import pytest
from pydantic import ValidationError

from apex.domain import (
    EntryPlan,
    EntryState,
    FuturesAccountInput,
    LeverageMode,
    PositionPlan,
    RiskMode,
    TargetLeg,
    TargetPlan,
)


def test_automatic_leverage_rejects_manual_value() -> None:
    with pytest.raises(ValidationError, match="manual leverage must be omitted"):
        FuturesAccountInput(
            wallet_balance=100,
            leverage_mode=LeverageMode.AUTOMATIC,
            manual_leverage=20,
            risk_mode=RiskMode.STANDARD,
            maximum_account_loss_percentage=3,
        )


def test_manual_leverage_requires_value() -> None:
    with pytest.raises(ValidationError, match="manual leverage is required"):
        FuturesAccountInput(
            wallet_balance=100,
            leverage_mode=LeverageMode.MANUAL,
            risk_mode=RiskMode.STANDARD,
            maximum_account_loss_percentage=3,
        )


def test_maximum_account_loss_amount() -> None:
    account = FuturesAccountInput(
        wallet_balance=100,
        leverage_mode=LeverageMode.AUTOMATIC,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=3,
    )

    assert account.maximum_account_loss_amount == 3


def test_ready_now_requires_current_price_inside_zone() -> None:
    with pytest.raises(ValidationError, match="READY_NOW requires"):
        EntryPlan(
            state=EntryState.READY_NOW,
            current_price=154,
            zone_low=153.20,
            zone_high=153.55,
            ideal_entry=153.31,
            maximum_chase_price=153.72,
        )


def test_missed_entry_requires_price_beyond_chase_limit() -> None:
    with pytest.raises(ValidationError, match="MISSED_ENTRY requires"):
        EntryPlan(
            state=EntryState.MISSED_ENTRY,
            current_price=153.60,
            zone_low=153.20,
            zone_high=153.55,
            ideal_entry=153.31,
            maximum_chase_price=153.72,
        )


def test_target_allocations_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="must total 100"):
        TargetPlan(
            targets=(
                TargetLeg(label="TP1", price=154.72, close_percentage=40),
                TargetLeg(label="TP2", price=156.10, close_percentage=35),
            )
        )


def test_position_margin_matches_notional_divided_by_leverage() -> None:
    plan = PositionPlan(
        leverage=20,
        position_notional=500,
        required_margin=25,
        wallet_exposure_percentage=25,
        planned_loss_amount=3,
        estimated_fees=0.50,
        estimated_slippage=0.25,
        liquidation_price=146,
    )

    assert plan.required_margin == 25


def test_incorrect_position_margin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="required margin must equal"):
        PositionPlan(
            leverage=20,
            position_notional=500,
            required_margin=30,
            wallet_exposure_percentage=30,
            planned_loss_amount=3,
            estimated_fees=0.50,
            estimated_slippage=0.25,
            liquidation_price=146,
        )
