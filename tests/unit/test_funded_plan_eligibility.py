"""Tests for non-authorizing futures-plan funded eligibility metadata."""

from datetime import date

from apex.domain import AccountPolicyDecision, AccountPolicyType
from apex.funded import (
    DrawdownModel,
    FundedPlanEligibilityReason,
    FundedPlanEligibilityState,
    ProviderPolicyBinding,
    evaluate_funded_plan_eligibility,
)


def _decision(*, approved: bool = True) -> AccountPolicyDecision:
    return AccountPolicyDecision(
        approved=approved,
        lockout_reasons=(),
        daily_drawdown_pct=0.0,
        total_drawdown_pct=0.0,
        projected_total_open_risk_pct=0.25,
        projected_directional_exposure_pct=0.25,
        projected_correlated_exposure_pct=0.25,
    )


def _binding(*, compatible: bool = True) -> ProviderPolicyBinding:
    return ProviderPolicyBinding(
        provider_id="EXAMPLE",
        provider_name="Example Funded",
        challenge_phase="PHASE_1",
        preset_sha256="a" * 64,
        verification_date=date(2026, 7, 1),
        drawdown_model=DrawdownModel.STATIC,
        weekend_trading_allowed=False,
        overnight_holding_allowed=True,
        news_trading_allowed=False,
        compatible=compatible,
        compatibility_reasons=(() if compatible else ("PROVIDER_POLICY_MISMATCH",)),
    )


def test_non_funded_policy_is_not_applicable() -> None:
    result = evaluate_funded_plan_eligibility(
        account_policy_type=AccountPolicyType.PAPER,
        account_policy_decision=None,
        provider_policy_binding=None,
    )

    assert result.state is FundedPlanEligibilityState.NOT_APPLICABLE
    assert result.reasons == (FundedPlanEligibilityReason.FUNDED_POLICY_REQUIRED,)
    assert result.execution_authorized is False


def test_missing_funded_evidence_is_incomplete() -> None:
    result = evaluate_funded_plan_eligibility(
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=None,
        provider_policy_binding=None,
    )

    assert result.state is FundedPlanEligibilityState.EVIDENCE_INCOMPLETE
    assert result.reasons == (
        FundedPlanEligibilityReason.ACCOUNT_POLICY_DECISION_REQUIRED,
        FundedPlanEligibilityReason.PROVIDER_POLICY_BINDING_REQUIRED,
    )
    assert result.execution_authorized is False


def test_blocked_policy_and_incompatible_binding_remain_incomplete() -> None:
    result = evaluate_funded_plan_eligibility(
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=_decision(approved=False),
        provider_policy_binding=_binding(compatible=False),
    )

    assert result.state is FundedPlanEligibilityState.EVIDENCE_INCOMPLETE
    assert result.reasons == (
        FundedPlanEligibilityReason.ACCOUNT_POLICY_BLOCKED,
        FundedPlanEligibilityReason.PROVIDER_POLICY_MISMATCH,
    )


def test_complete_funded_evidence_is_review_eligible_but_not_authorized() -> None:
    result = evaluate_funded_plan_eligibility(
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=_decision(),
        provider_policy_binding=_binding(),
    )

    assert result.state is FundedPlanEligibilityState.ELIGIBLE_FOR_FUNDED_REVIEW
    assert result.reasons == ()
    assert result.provider_name == "Example Funded"
    assert result.challenge_phase == "PHASE_1"
    assert result.provider_preset_sha256 == "a" * 64
    assert result.execution_authorized is False
