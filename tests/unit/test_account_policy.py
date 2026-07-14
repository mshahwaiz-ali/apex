"""Tests for account-policy validation and deterministic lockouts."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.config import load_account_policies_config
from apex.domain import (
    AccountLockoutReason,
    AccountPolicy,
    AccountPolicyState,
    AccountPolicyType,
    evaluate_account_policy,
)


def _policy(**overrides: object) -> AccountPolicy:
    values: dict[str, object] = {
        "type": AccountPolicyType.FUNDED,
        "initial_balance": 50_000,
        "external_daily_drawdown_limit_pct": 5,
        "external_total_drawdown_limit_pct": 10,
        "internal_daily_stop_pct": 1,
        "internal_total_drawdown_buffer_pct": 2,
        "maximum_risk_per_trade_pct": 0.25,
        "maximum_total_open_risk_pct": 0.75,
        "maximum_directional_exposure_pct": 20,
        "maximum_correlated_exposure_pct": 15,
        "maximum_trades_per_day": 3,
        "maximum_consecutive_losses": 2,
        "required_stop_loss": True,
        "weekend_trading_allowed": False,
    }
    values.update(overrides)
    return AccountPolicy.model_validate(values)


def _state(**overrides: object) -> AccountPolicyState:
    values: dict[str, object] = {
        "current_balance": 50_000,
        "current_equity": 50_000,
        "start_of_day_equity": 50_000,
        "trades_today": 0,
        "consecutive_losses": 0,
        "total_open_risk_pct": 0,
        "directional_exposure_pct": 0,
        "correlated_exposure_pct": 0,
        "proposed_risk_pct": 0.25,
        "proposed_has_stop_loss": True,
    }
    values.update(overrides)
    return AccountPolicyState.model_validate(values)


def test_default_policy_configuration_loads() -> None:
    config = load_account_policies_config(Path("config/account_policies.yaml"))

    assert config.policy_for().type is AccountPolicyType.PAPER
    assert config.policy_for("FUNDED_GENERIC").type is AccountPolicyType.FUNDED


def test_invalid_internal_daily_stop_is_rejected() -> None:
    with pytest.raises(ValidationError, match="internal daily stop"):
        _policy(internal_daily_stop_pct=6)


def test_invalid_total_drawdown_buffer_is_rejected() -> None:
    with pytest.raises(ValidationError, match="total-drawdown buffer"):
        _policy(internal_total_drawdown_buffer_pct=10)


def test_daily_drawdown_boundary_locks_account() -> None:
    decision = evaluate_account_policy(_policy(), _state(current_equity=49_500))

    assert decision.approved is False
    assert AccountLockoutReason.DAILY_DRAWDOWN in decision.lockout_reasons


def test_total_drawdown_internal_buffer_locks_account() -> None:
    decision = evaluate_account_policy(
        _policy(),
        _state(current_equity=46_000, start_of_day_equity=46_000),
    )

    assert decision.total_drawdown_pct == pytest.approx(8)
    assert AccountLockoutReason.TOTAL_DRAWDOWN in decision.lockout_reasons


def test_trade_and_loss_boundaries_lock_account() -> None:
    decision = evaluate_account_policy(
        _policy(),
        _state(trades_today=3, consecutive_losses=2),
    )

    assert AccountLockoutReason.MAXIMUM_TRADES in decision.lockout_reasons
    assert AccountLockoutReason.CONSECUTIVE_LOSSES in decision.lockout_reasons


def test_open_risk_and_required_stop_are_enforced() -> None:
    decision = evaluate_account_policy(
        _policy(),
        _state(total_open_risk_pct=0.6, proposed_risk_pct=0.25, proposed_has_stop_loss=False),
    )

    assert AccountLockoutReason.MAXIMUM_OPEN_RISK in decision.lockout_reasons
    assert AccountLockoutReason.STOP_LOSS_REQUIRED in decision.lockout_reasons


def test_safe_account_state_is_approved() -> None:
    decision = evaluate_account_policy(_policy(), _state())

    assert decision.approved is True
    assert decision.lockout_reasons == ()
