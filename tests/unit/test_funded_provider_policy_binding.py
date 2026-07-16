"""Tests for funded provider-policy binding and session restrictions."""

from datetime import date

from apex.domain import (
    AccountLockoutReason,
    AccountPolicy,
    AccountPolicyState,
    AccountPolicyType,
    evaluate_account_policy,
)
from apex.funded import DrawdownModel, FundedProviderLimitPreset, bind_provider_policy


def _preset(**overrides: object) -> FundedProviderLimitPreset:
    payload: dict[str, object] = {
        "provider_id": "EXAMPLE",
        "provider_name": "Example Funded",
        "challenge_phase": "PHASE_1",
        "verified_on": date(2026, 7, 1),
        "source_reference": "operator-supplied-reference",
        "drawdown_model": DrawdownModel.STATIC,
        "external_daily_drawdown_limit_pct": 5.0,
        "external_total_drawdown_limit_pct": 10.0,
        "maximum_trades_per_day": 3,
        "weekend_trading_allowed": False,
        "overnight_holding_allowed": False,
        "news_trading_allowed": False,
        "limits_verified": True,
    }
    payload.update(overrides)
    return FundedProviderLimitPreset.model_validate(payload).with_verified_hash()


def _policy(**overrides: object) -> AccountPolicy:
    preset = _preset()
    payload: dict[str, object] = {
        "type": AccountPolicyType.FUNDED,
        "provider_name": preset.provider_name,
        "challenge_phase": preset.challenge_phase,
        "provider_preset_sha256": preset.preset_sha256,
        "initial_balance": 50_000.0,
        "external_daily_drawdown_limit_pct": 5.0,
        "external_total_drawdown_limit_pct": 10.0,
        "internal_daily_stop_pct": 1.0,
        "internal_total_drawdown_buffer_pct": 2.0,
        "maximum_risk_per_trade_pct": 0.25,
        "maximum_total_open_risk_pct": 0.75,
        "maximum_directional_exposure_pct": 20.0,
        "maximum_correlated_exposure_pct": 15.0,
        "maximum_trades_per_day": 3,
        "maximum_consecutive_losses": 2,
        "required_stop_loss": True,
        "weekend_trading_allowed": False,
        "overnight_holding_allowed": False,
        "news_trading_allowed": False,
    }
    payload.update(overrides)
    return AccountPolicy.model_validate(payload)


def _state(**overrides: object) -> AccountPolicyState:
    preset = _preset()
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
        "active_provider_name": preset.provider_name,
        "active_challenge_phase": preset.challenge_phase,
        "active_provider_preset_sha256": preset.preset_sha256,
    }
    payload.update(overrides)
    return AccountPolicyState.model_validate(payload)


def test_news_and_overnight_restrictions_lock_funded_policy() -> None:
    decision = evaluate_account_policy(
        _policy(),
        _state(is_news_event_window=True, proposed_holds_overnight=True),
    )

    assert AccountLockoutReason.NEWS_TRADING_RESTRICTED in decision.lockout_reasons
    assert AccountLockoutReason.OVERNIGHT_HOLDING_RESTRICTED in decision.lockout_reasons


def test_provider_phase_hash_and_freshness_are_enforced() -> None:
    mismatch = evaluate_account_policy(
        _policy(),
        _state(active_challenge_phase="PHASE_2"),
    )
    stale = evaluate_account_policy(_policy(), _state(provider_limits_fresh=False))

    assert AccountLockoutReason.PROVIDER_POLICY_MISMATCH in mismatch.lockout_reasons
    assert AccountLockoutReason.PROVIDER_LIMITS_STALE in stale.lockout_reasons


def test_compatible_binding_is_deterministic_and_non_authorizing() -> None:
    preset = _preset()
    first = bind_provider_policy(preset, _policy(), as_of=date(2026, 7, 16), maximum_age_days=30)
    second = bind_provider_policy(preset, _policy(), as_of=date(2026, 7, 16), maximum_age_days=30)

    assert first == second
    assert first.compatible is True
    assert first.execution_authorized is False
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_stale_and_mismatched_bindings_are_rejected() -> None:
    preset = _preset()
    stale = bind_provider_policy(preset, _policy(), as_of=date(2026, 8, 2), maximum_age_days=30)
    mismatch = bind_provider_policy(
        preset,
        _policy(challenge_phase="PHASE_2"),
        as_of=date(2026, 7, 16),
        maximum_age_days=30,
    )

    assert stale.compatible is False
    assert "PROVIDER_LIMITS_STALE" in stale.compatibility_reasons
    assert mismatch.compatible is False
    assert "CHALLENGE_PHASE_MISMATCH" in mismatch.compatibility_reasons


def test_paper_and_personal_policies_keep_permissive_session_defaults() -> None:
    for policy_type in (AccountPolicyType.PAPER, AccountPolicyType.PERSONAL):
        policy = _policy(
            type=policy_type,
            provider_name=None,
            challenge_phase=None,
            provider_preset_sha256=None,
            weekend_trading_allowed=True,
            overnight_holding_allowed=True,
            news_trading_allowed=True,
        )
        decision = evaluate_account_policy(
            policy,
            _state(
                active_provider_name=None,
                active_challenge_phase=None,
                active_provider_preset_sha256=None,
                is_news_event_window=True,
                proposed_holds_overnight=True,
            ),
        )

        assert decision.approved is True
        assert decision.lockout_reasons == ()