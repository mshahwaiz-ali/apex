"""Attach non-authorizing funded eligibility metadata to futures-plan results."""

from __future__ import annotations

from apex.application.risk_approval import build_futures_plan_result
from apex.config import FuturesProductConfig, StrategyApprovalConfig
from apex.domain import (
    AccountPolicy,
    AccountPolicyDecision,
    AccountPolicyState,
    FuturesAccountInput,
    evaluate_account_policy,
)
from apex.funded import ProviderPolicyBinding, evaluate_funded_plan_eligibility
from apex.risk.contracts import RiskApprovedSetup

__all__ = ["build_funded_futures_plan_result"]


def build_funded_futures_plan_result(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,
    *,
    account_policy: AccountPolicy,
    account_policy_state: AccountPolicyState,
    provider_policy_binding: ProviderPolicyBinding | None,
    product_config: FuturesProductConfig | None = None,
    strategy_approval_config: StrategyApprovalConfig | None = None,
    historical_evidence_available: bool = False,
) -> dict[str, object]:
    """Build a futures-plan result with explicit funded-review eligibility metadata."""

    policy_decision = _policy_decision(
        account=account,
        policy=account_policy,
        state=account_policy_state,
    )
    result = build_futures_plan_result(
        setup,
        account,
        product_config=product_config,
        strategy_approval_config=strategy_approval_config,
        account_policy=account_policy,
        account_policy_state=account_policy_state,
        historical_evidence_available=historical_evidence_available,
    )
    eligibility = evaluate_funded_plan_eligibility(
        account_policy_type=account_policy.type,
        account_policy_decision=policy_decision,
        provider_policy_binding=provider_policy_binding,
    )
    result["funded_eligibility"] = eligibility.model_dump(mode="json")
    result["execution_authorized"] = False
    return result


def _policy_decision(
    *,
    account: FuturesAccountInput,
    policy: AccountPolicy,
    state: AccountPolicyState,
) -> AccountPolicyDecision:
    proposed_state = state.model_copy(
        update={
            "proposed_risk_pct": account.maximum_account_loss_percentage,
            "proposed_has_stop_loss": True,
        }
    )
    return evaluate_account_policy(policy, proposed_state)
