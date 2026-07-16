from datetime import UTC, date, datetime

from apex.domain import AccountPolicyDecision, AccountPolicyType, RiskMode
from apex.execution.contracts import KillSwitchState
from apex.funded import (
    DrawdownModel,
    FundedProviderLimits,
    FundedReadinessReason,
    ManualExecutionChecklist,
    ProviderPolicyBinding,
    evaluate_funded_readiness,
)
from apex.validation import ForwardValidationReport, ProductionEligibility


def _policy_decision(*, approved: bool = True) -> AccountPolicyDecision:
    return AccountPolicyDecision(
        approved=approved,
        lockout_reasons=(),
        daily_drawdown_pct=0.0,
        total_drawdown_pct=0.0,
        projected_total_open_risk_pct=0.25,
        projected_directional_exposure_pct=0.25,
        projected_correlated_exposure_pct=0.25,
    )


def _validation(
    eligibility: ProductionEligibility = ProductionEligibility.READY_FOR_FUNDED_REVIEW,
) -> ForwardValidationReport:
    return ForwardValidationReport(
        schema_version=1,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
        eligibility=eligibility,
        reasons=(),
        closed_paper_trades=40,
        modeled_trades=100,
        win_rate_deviation=0.02,
        expectancy_deviation=0.10,
        drawdown_increase=0.05,
    )


def _limits(*, verified: bool = True) -> FundedProviderLimits:
    return FundedProviderLimits(
        provider_name="verified-provider",
        verified_on=date(2026, 7, 14),
        external_daily_drawdown_limit_pct=5.0,
        external_total_drawdown_limit_pct=10.0,
        maximum_trades_per_day=3,
        limits_verified=verified,
    )


def _binding(*, compatible: bool = True) -> ProviderPolicyBinding:
    return ProviderPolicyBinding(
        provider_id="VERIFIED_PROVIDER",
        provider_name="verified-provider",
        challenge_phase="phase-1",
        preset_sha256="0" * 64,
        verification_date=date(2026, 7, 14),
        drawdown_model=DrawdownModel.STATIC,
        weekend_trading_allowed=False,
        overnight_holding_allowed=False,
        news_trading_allowed=False,
        compatible=compatible,
        compatibility_reasons=() if compatible else ("PROVIDER_POLICY_MISMATCH",),
        execution_authorized=False,
    )


def _checklist(*, complete: bool = True) -> ManualExecutionChecklist:
    return ManualExecutionChecklist(
        analysis_reviewed=complete,
        risk_reviewed=complete,
        account_state_reviewed=complete,
        order_or_fill_verified=complete,
        lifecycle_recorded=complete,
    )


def test_funded_readiness_passes_only_when_all_gates_pass() -> None:
    report = evaluate_funded_readiness(
        provider_limits=_limits(),
        forward_validation=_validation(),
        risk_mode=RiskMode.STANDARD,
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=_policy_decision(),
        provider_policy_binding=_binding(),
        daily_lockout_verified=True,
        total_buffer_verified=True,
        pre_trade_checklist=_checklist(),
        post_trade_checklist=_checklist(),
        kill_switch_state=KillSwitchState.ENABLED,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.ready is True
    assert report.reasons == ()


def test_funded_readiness_requires_provider_policy_binding() -> None:
    report = evaluate_funded_readiness(
        provider_limits=_limits(),
        forward_validation=_validation(),
        risk_mode=RiskMode.STANDARD,
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=_policy_decision(),
        daily_lockout_verified=True,
        total_buffer_verified=True,
        pre_trade_checklist=_checklist(),
        post_trade_checklist=_checklist(),
        kill_switch_state=KillSwitchState.ENABLED,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.ready is False
    assert FundedReadinessReason.PROVIDER_POLICY_BINDING_REQUIRED in report.reasons




def test_funded_readiness_requires_verified_provider_and_p1() -> None:
    report = evaluate_funded_readiness(
        provider_limits=_limits(verified=False),
        forward_validation=_validation(ProductionEligibility.PAPER_ONLY),
        risk_mode=RiskMode.STANDARD,
        account_policy_type=AccountPolicyType.FUNDED,
        account_policy_decision=_policy_decision(),
        provider_policy_binding=_binding(),
        daily_lockout_verified=True,
        total_buffer_verified=True,
        pre_trade_checklist=_checklist(),
        post_trade_checklist=_checklist(),
        kill_switch_state=KillSwitchState.ENABLED,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.ready is False
    assert FundedReadinessReason.PROVIDER_LIMITS_UNVERIFIED in report.reasons
    assert FundedReadinessReason.FORWARD_VALIDATION_INCOMPLETE in report.reasons
