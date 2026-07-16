"""Focused fail-closed tests for funded account identity and provider bindings."""

from datetime import date

import pytest
from pydantic import ValidationError

from apex.domain import (
    AccountLockoutReason,
    AccountPolicy,
    AccountPolicyState,
    AccountPolicyType,
    evaluate_account_policy,
)
from apex.funded import DrawdownModel, ProviderPolicyBinding


PRESET_SHA = "a" * 64


def _policy() -> AccountPolicy:
    return AccountPolicy(
        type=AccountPolicyType.FUNDED,
        provider_name="Example Funded",
        challenge_phase="PHASE_1",
        provider_preset_sha256=PRESET_SHA,
        initial_balance=50_000.0,
        external_daily_drawdown_limit_pct=5.0,
        external_total_drawdown_limit_pct=10.0,
        internal_daily_stop_pct=1.0,
        internal_total_drawdown_buffer_pct=2.0,
        maximum_risk_per_trade_pct=0.25,
        maximum_total_open_risk_pct=0.75,
        maximum_directional_exposure_pct=20.0,
        maximum_correlated_exposure_pct=15.0,
        maximum_trades_per_day=3,
        maximum_consecutive_losses=2,
        weekend_trading_allowed=False,
        overnight_holding_allowed=False,
        news_trading_allowed=False,
    )


def _state(**overrides: object) -> AccountPolicyState:
    payload: dict[str, object] = {
        "current_balance": 50_000.0,
        "current_equity": 50_000.0,
        "start_of_day_equity": 50_000.0,
        "trades_today": 0,
        "consecutive_losses": 0,
        "total_open_risk_pct": 0.0,
        "directional_exposure_pct": 0.0,
        "correlated_exposure_pct": 0.0,
        "proposed_risk_pct": 0.25,
        "active_provider_name": "Example Funded",
        "active_challenge_phase": "PHASE_1",
        "active_provider_preset_sha256": PRESET_SHA,
        "provider_limits_fresh": True,
    }
    payload.update(overrides)
    return AccountPolicyState.model_validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    [
        "active_provider_name",
        "active_challenge_phase",
        "active_provider_preset_sha256",
    ],
)
def test_missing_required_funded_identity_locks_account(missing_field: str) -> None:
    decision = evaluate_account_policy(_policy(), _state(**{missing_field: None}))

    assert decision.approved is False
    assert AccountLockoutReason.PROVIDER_POLICY_MISMATCH in decision.lockout_reasons


def test_exact_funded_identity_remains_approved() -> None:
    decision = evaluate_account_policy(_policy(), _state())

    assert decision.approved is True
    assert decision.lockout_reasons == ()


def test_provider_binding_cannot_be_constructed_as_authorizing() -> None:
    with pytest.raises(ValidationError, match="execution_authorized"):
        ProviderPolicyBinding(
            provider_id="EXAMPLE",
            provider_name="Example Funded",
            challenge_phase="PHASE_1",
            preset_sha256=PRESET_SHA,
            verification_date=date(2026, 7, 1),
            drawdown_model=DrawdownModel.STATIC,
            weekend_trading_allowed=False,
            overnight_holding_allowed=False,
            news_trading_allowed=False,
            compatible=True,
            execution_authorized=True,
        )
