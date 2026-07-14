"""Integration tests for combined risk-mode and account-policy approval."""

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application import build_futures_plan_result
from apex.config import load_account_policies_config
from apex.domain import AccountPolicyState, FuturesAccountInput, RiskMode


def _setup() -> SimpleNamespace:
    return SimpleNamespace(
        decision_time=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
        direction=SimpleNamespace(value="long"),
        confidence_score=85.0,
        entry=SimpleNamespace(
            lower=100.0,
            upper=101.0,
            preferred=100.5,
            current_price=100.6,
            maximum_chase_price=101.5,
            current_price_inside_zone=True,
        ),
        stop_loss=SimpleNamespace(
            price=98.0,
            quality_score=0.8,
            rationale=("structure invalidation",),
        ),
        take_profits=(
            SimpleNamespace(label="TP1", price=103.0, partial_close_pct=60.0),
            SimpleNamespace(label="TP2", price=106.0, partial_close_pct=40.0),
        ),
        position_size=SimpleNamespace(
            required_leverage=2.0,
            notional_value=500.0,
            risk_amount=2.5,
        ),
        leverage=SimpleNamespace(liquidation_price_at_maximum=50.0),
    )


def _state(**overrides: object) -> AccountPolicyState:
    values: dict[str, object] = {
        "current_balance": 50000.0,
        "current_equity": 50000.0,
        "start_of_day_equity": 50000.0,
        "trades_today": 0,
        "consecutive_losses": 0,
        "total_open_risk_pct": 0.0,
        "directional_exposure_pct": 0.0,
        "correlated_exposure_pct": 0.0,
        "is_weekend": False,
        "session": "LONDON",
        "proposed_risk_pct": 0.0,
        "proposed_has_stop_loss": True,
    }
    values.update(overrides)
    return AccountPolicyState.model_validate(values)


def test_approved_plan_serializes_risk_and_policy_snapshots() -> None:
    policies = load_account_policies_config("config/account_policies.yaml")
    policy = policies.policy_for("FUNDED_GENERIC")
    account = FuturesAccountInput(
        wallet_balance=50000.0,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.25,
    )

    result = build_futures_plan_result(
        _setup(),
        account,
        account_policy=policy,
        account_policy_state=_state(),
    )

    assert result["status"] == "APPROVED"
    assert result["risk_mode"] == "STANDARD"
    assert result["risk_mode_config"]["account_loss_percentage"] == 0.25
    assert result["account_policy"]["type"] == "FUNDED"
    assert result["account_policy_decision"]["approved"] is True


def test_account_policy_lockout_rejects_plan_before_position_approval() -> None:
    policies = load_account_policies_config("config/account_policies.yaml")
    policy = policies.policy_for("FUNDED_GENERIC")
    account = FuturesAccountInput(
        wallet_balance=50000.0,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.25,
    )

    result = build_futures_plan_result(
        _setup(),
        account,
        account_policy=policy,
        account_policy_state=_state(current_equity=49250.0),
    )

    assert result["status"] == "REJECTED"
    assert "account policy lockout: DAILY_DRAWDOWN" in result["reasons"]


def test_risk_mode_limit_rejects_oversized_account_loss_override() -> None:
    account = FuturesAccountInput(
        wallet_balance=10000.0,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.5,
    )

    result = build_futures_plan_result(_setup(), account)

    assert result["status"] == "REJECTED"
    assert any("STANDARD mode limit 0.25%" in reason for reason in result["reasons"])


def test_policy_and_state_must_be_supplied_together() -> None:
    policies = load_account_policies_config("config/account_policies.yaml")
    account = FuturesAccountInput(
        wallet_balance=50000.0,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.25,
    )

    result = build_futures_plan_result(
        _setup(),
        account,
        account_policy=policies.policy_for("FUNDED_GENERIC"),
    )

    assert result["status"] == "REJECTED"
    assert result["reasons"] == [
        "account policy and account policy state must be supplied together"
    ]
