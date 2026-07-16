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
    "evaluate_funded_plan