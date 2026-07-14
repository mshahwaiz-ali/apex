from __future__ import annotations

import pytest
from pydantic import ValidationError

from apex.domain import (
    SpotAccountInput,
    SpotBalanceInput,
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


def test_spot_account_serialization_is_deterministic() -> None:
    account = SpotAccountInput(
        quote_asset="USDT",
        available_quote_balance=700.0,
        total_spot_equity=1000.0,
        current_spot_exposure=300.0,
        open_position_count=1,
        balances=(SpotBalanceInput(asset="BTC", available=0.01),),
    )

    assert account.model_dump(mode="json") == {
        "quote_asset": "USDT",
        "available_quote_balance": 700.0,
        "total_spot_equity": 1000.0,
        "current_spot_exposure": 300.0,
        "open_position_count": 1,
        "balances": [{"asset": "BTC", "available": 0.01, "reserved": 0.0}],
    }


def test_spot_account_rejects_duplicate_balance_assets_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="spot balance assets must be unique"):
        SpotAccountInput(
            quote_asset="USDT",
            available_quote_balance=1000.0,
            total_spot_equity=1000.0,
            balances=(
                SpotBalanceInput(asset="BTC", available=0.01),
                SpotBalanceInput(asset="btc", available=0.02),
            ),
        )


def test_spot_entry_plan_supports_only_planned_long_scale_ins() -> None:
    plan = SpotEntryPlan(
        state=SpotEntryState.READY_NOW,
        current_price=100.0,
        entries=(
            SpotEntryLeg(label="E1", price=100.0, allocation_percentage=40.0),
            SpotEntryLeg(label="E2", price=95.0, allocation_percentage=35.0),
            SpotEntryLeg(
                label="E3",
                price=90.0,
                allocation_percentage=25.0,
                requires_confirmation=True,
            ),
        ),
        maximum_chase_price=102.0,
        invalidation_price=85.0,
    )

    assert plan.entries[2].requires_confirmation is True


def test_spot_entry_plan_rejects_uncontrolled_averaging_down() -> None:
    with pytest.raises(ValidationError, match="allocation percentages must total 100"):
        SpotEntryPlan(
            state=SpotEntryState.WATCH,
            current_price=100.0,
            entries=(
                SpotEntryLeg(label="E1", price=100.0, allocation_percentage=40.0),
                SpotEntryLeg(label="E2", price=95.0, allocation_percentage=35.0),
            ),
            maximum_chase_price=102.0,
            invalidation_price=90.0,
        )


def test_spot_stop_plan_keeps_protection_below_structural_invalidation() -> None:
    plan = SpotStopPlan(
        structural_invalidation_price=90.0,
        protective_stop_price=89.0,
        thesis_failure_reason="daily structure failed",
    )

    assert plan.market_regime_exit_required is True


def test_spot_stop_plan_rejects_invalid_long_geometry() -> None:
    with pytest.raises(ValidationError, match="cannot exceed structural invalidation"):
        SpotStopPlan(
            structural_invalidation_price=90.0,
            protective_stop_price=91.0,
            thesis_failure_reason="daily structure failed",
        )


def test_spot_targets_must_sell_exactly_the_full_position_in_order() -> None:
    plan = SpotTargetPlan(
        targets=(
            SpotTargetLeg(
                label="TP1",
                price=110.0,
                sell_percentage=40.0,
                rationale="first resistance",
            ),
            SpotTargetLeg(
                label="TP2",
                price=120.0,
                sell_percentage=60.0,
                rationale="major resistance",
            ),
        )
    )

    assert sum(target.sell_percentage for target in plan.targets) == 100.0


def test_spot_position_plan_contains_no_futures_geometry() -> None:
    plan = SpotPositionPlan(
        average_entry_price=100.0,
        quantity=2.0,
        capital_allocated=200.0,
        allocation_percentage_of_equity=20.0,
        planned_loss_amount=20.0,
        planned_loss_percentage_of_equity=2.0,
        remaining_quote_reserve=300.0,
    )

    payload = plan.model_dump(mode="json")
    assert "leverage" not in payload
    assert "liquidation_price" not in payload
    assert "required_margin" not in payload


def test_spot_terminal_lifecycle_cannot_retain_open_quantity() -> None:
    with pytest.raises(ValidationError, match="cannot retain open quantity"):
        SpotLifecycleSnapshot(
            state=SpotLifecycleState.CLOSED,
            open_quantity=1.0,
        )


def test_spot_active_lifecycle_requires_open_quantity() -> None:
    with pytest.raises(ValidationError, match="require open quantity"):
        SpotLifecycleSnapshot(
            state=SpotLifecycleState.FILLED,
            open_quantity=0.0,
        )
