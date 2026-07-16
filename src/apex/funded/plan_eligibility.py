"""Non-authorizing funded eligibility metadata for futures plans."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from apex.domain import AccountPolicyDecision, AccountPolicyType
from apex.funded.provider_policy_binding import ProviderPolicyBinding

__all__ = [
    "FundedPlanEligibility",
    "FundedPlanEligibilityReason",
    "FundedPlanEligibilityState",
    "evaluate_funded_plan_eligibility",
]


class FundedPlanEligibilityState(StrEnum):
    """Stable funded-eligibility states for plan serialization."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    ELIGIBLE_FOR_FUNDED_REVIEW = "ELIGIBLE_FOR_FUNDED_REVIEW"


class FundedPlanEligibilityReason(StrEnum):
    """Stable blockers that prevent funded-review eligibility."""

    FUNDED_POLICY_REQUIRED = "FUNDED_POLICY_REQUIRED"
    ACCOUNT_POLICY_DECISION_REQUIRED = "ACCOUNT_POLICY_DECISION_REQUIRED"
    ACCOUNT_POLICY_BLOCKED = "ACCOUNT_POLICY_BLOCKED"
    PROVIDER_POLICY_BINDING_REQUIRED = "PROVIDER_POLICY_BINDING_REQUIRED"
    PROVIDER_POLICY_MISMATCH = "PROVIDER_POLICY_MISMATCH"


class FundedPlanEligibility(BaseModel):
    """Serializable eligibility metadata that never authorizes execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: FundedPlanEligibilityState
    reasons: tuple[FundedPlanEligibilityReason, ...] = ()
    provider_name: str | None = None
    challenge_phase: str | None = None
    provider_preset_sha256: str | None = None
    execution_authorized: Literal[False] = False


def evaluate_funded_plan_eligibility(
    *,
    account_policy_type: AccountPolicyType | None,
    account_policy_decision: AccountPolicyDecision | None,
    provider_policy_binding: ProviderPolicyBinding | None,
) -> FundedPlanEligibility:
    """Classify funded-review eligibility without granting execution permission."""

    if account_policy_type is not AccountPolicyType.FUNDED:
        return FundedPlanEligibility(
            state=FundedPlanEligibilityState.NOT_APPLICABLE,
            reasons=(FundedPlanEligibilityReason.FUNDED_POLICY_REQUIRED,),
        )

    reasons: list[FundedPlanEligibilityReason] = []
    if account_policy_decision is None:
        reasons.append(FundedPlanEligibilityReason.ACCOUNT_POLICY_DECISION_REQUIRED)
    elif not account_policy_decision.approved:
        reasons.append(FundedPlanEligibilityReason.ACCOUNT_POLICY_BLOCKED)

    if provider_policy_binding is None:
        reasons.append(FundedPlanEligibilityReason.PROVIDER_POLICY_BINDING_REQUIRED)
    elif not provider_policy_binding.compatible:
        reasons.append(FundedPlanEligibilityReason.PROVIDER_POLICY_MISMATCH)

    unique_reasons = tuple(dict.fromkeys(reasons))
    if unique_reasons:
        return FundedPlanEligibility(
            state=FundedPlanEligibilityState.EVIDENCE_INCOMPLETE,
            reasons=unique_reasons,
            provider_name=(
                provider_policy_binding.provider_name
                if provider_policy_binding is not None
                else None
            ),
            challenge_phase=(
                provider_policy_binding.challenge_phase
                if provider_policy_binding is not None
                else None
            ),
            provider_preset_sha256=(
                provider_policy_binding.preset_sha256
                if provider_policy_binding is not None
                else None
            ),
        )

    assert provider_policy_binding is not None
    return FundedPlanEligibility(
        state=FundedPlanEligibilityState.ELIGIBLE_FOR_FUNDED_REVIEW,
        provider_name=provider_policy_binding.provider_name,
        challenge_phase=provider_policy_binding.challenge_phase,
        provider_preset_sha256=provider_policy_binding.preset_sha256,
    )
