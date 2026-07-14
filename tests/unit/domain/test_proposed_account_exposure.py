from __future__ import annotations

from datetime import date

import pytest

from apex.application.account_state import AccountStateSnapshot
from apex.domain import (
    AccountLockoutReason,
    AccountPolicy,
    AccountPolicyState,
    AccountPolicyType,
    evaluate_account_policy,
)


def _policy() -> AccountPolicy:
    return AccountPolicy(
        type=AccountPolicyType.PAPER,
        initial_balance=1000.0,
        external_daily_drawdown_limit_pct=5.0,
        external_total_drawdown_limit_pct=10.0,
        internal_daily_stop_pct=3.0,
        internal_total_drawdown_buffer_pct=2.0,
        maximum_risk_per_trade_pct=1.0,
        maximum_total_open_risk_pct=3.0,
        maximum_directional_exposure_pct=1.0,
        maximum_correlated_exposure_pct=0.75,
        maximum_trades_per_day=5,
        maximum_consecutive_losses=3,
    )


def _state(**updates: float) -> AccountPolicyState:
    values: dict[str, object] = {
        "current_balance": 1000.0,
        "current_equity": 1000.0,
        "start_of_day_equity": 1000.0,
        "trades_today": 0,
        "consecutive_losses": 0,
        "total_open_risk_pct": 1.0,
        "directional_exposure_pct": 0.8,
        "correlated_exposure_pct": 0.5,
        "proposed_risk_pct": 0.5,
        "proposed_directional_exposure_pct": 0.3,
        "proposed_correlated_exposure_pct": 0.3,
    }
    values.update(updates)
    return AccountPolicyState.model_validate(values)


def test_policy_rejects_projected_directional_and_correlated_exposure() -> None:
    decision = evaluate_account_policy(_policy(), _state())

    assert decision.approved is False
    assert AccountLockoutReason.MAXIMUM_DIRECTIONAL_EXPOSURE in decision.lockout_reasons
    assert AccountLockoutReason.MAXIMUM_CORRELATED_EXPOSURE in decision.lockout_reasons
    assert decision.projected_total_open_risk_pct == pytest.approx(1.5)
    assert decision.projected_directional_exposure_pct == pytest.approx(1.1)
    assert decision.projected_correlated_exposure_pct == pytest.approx(0.8)


def test_policy_approves_when_projected_exposure_remains_within_limits() -> None:
    decision = evaluate_account_policy(
        _policy(),
        _state(
            proposed_directional_exposure_pct=0.2,
            proposed_correlated_exposure_pct=0.2,
        ),
    )

    assert decision.approved is True
    assert decision.lockout_reasons == ()
    assert decision.projected_directional_exposure_pct == pytest.approx(1.0)
    assert decision.projected_correlated_exposure_pct == pytest.approx(0.7)


def test_proposed_exposure_cannot_exceed_proposed_risk() -> None:
    with pytest.raises(ValueError, match="proposed directional exposure"):
        _state(proposed_directional_exposure_pct=0.6)


def test_snapshot_builds_policy_state_with_explicit_proposed_exposure() -> None:
    snapshot = AccountStateSnapshot(
        policy_name="PAPER",
        trading_day=date(2026, 7, 14),
        current_balance=1000.0,
        current_equity=1000.0,
        start_of_day_equity=1000.0,
        total_open_risk_pct=1.0,
        directional_exposure_pct=0.5,
        correlated_exposure_pct=0.25,
    )

    state = snapshot.for_policy_evaluation(
        proposed_risk_pct=0.5,
        proposed_directional_exposure_pct=0.5,
        proposed_correlated_exposure_pct=0.25,
        proposed_has_stop_loss=True,
    )

    assert state.proposed_directional_exposure_pct == pytest.approx(0.5)
    assert state.proposed_correlated_exposure_pct == pytest.approx(0.25)
