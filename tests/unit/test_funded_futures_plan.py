"""Tests for funded futures-plan eligibility metadata integration."""

from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest

from apex.application import funded_futures_plan
from apex.domain import (
    AccountPolicy,
    AccountPolicyState,
    AccountPolicyType,
    FuturesAccountInput,
    LeverageMode,
    RiskMode,
)
from apex.funded import DrawdownModel, ProviderPolicyBinding
from apex.risk import RiskApprovedSetup

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


def _account() -> FuturesAccountInput:
    return FuturesAccountInput(
        wallet_balance=50_000.0,
        leverage_mode=LeverageMode.AUTOMATIC,
        risk_mode=RiskMode.STANDARD,
        maximum_account_loss_percentage=0.25,
    )


def _binding() -> ProviderPolicyBinding:
    return ProviderPolicyBinding(
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
    )


def _setup() -> RiskApprovedSetup:
    return cast(RiskApprovedSetup, SimpleNamespace())


def _stub_builder(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setattr(
        funded_futures_plan,
        "build_futures_plan_result",
        lambda *args, **kwargs: dict(payload),
    )


def test_approved_funded_plan_is_review_eligible_but_not_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_builder(monkeypatch, {"status": "APPROVED"})

    result = funded_futures_plan.build_funded_futures_plan_result(
        _setup(),
        _account(),
        account_policy=_policy(),
        account_policy_state=_state(),
        provider_policy_binding=_binding(),
    )

    eligibility = cast(dict[str, object], result["funded_eligibility"])
    assert eligibility["state"] == "ELIGIBLE_FOR_FUNDED_REVIEW"
    assert eligibility["execution_authorized"] is False
    assert result["execution_authorized"] is False


def test_missing_binding_marks_result_evidence_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_builder(monkeypatch, {"status": "APPROVED"})

    result = funded_futures_plan.build_funded_futures_plan_result(
        _setup(),
        _account(),
        account_policy=_policy(),
        account_policy_state=_state(),
        provider_policy_binding=None,
    )

    eligibility = cast(dict[str, object], result["funded_eligibility"])
    assert eligibility["state"] == "EVIDENCE_INCOMPLETE"
    assert eligibility["reasons"] == ["PROVIDER_POLICY_BINDING_REQUIRED"]
    assert result["execution_authorized"] is False


def test_blocked_account_state_keeps_rejection_and_funded_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_builder(monkeypatch, {"status": "REJECTED", "reasons": ["account policy lockout"]})

    result = funded_futures_plan.build_funded_futures_plan_result(
        _setup(),
        _account(),
        account_policy=_policy(),
        account_policy_state=_state(provider_limits_fresh=False),
        provider_policy_binding=_binding(),
    )

    eligibility = cast(dict[str, object], result["funded_eligibility"])
    assert result["status"] == "REJECTED"
    assert eligibility["state"] == "EVIDENCE_INCOMPLETE"
    assert eligibility["reasons"] == ["ACCOUNT_POLICY_BLOCKED"]
    assert result["execution_authorized"] is False
