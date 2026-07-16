"""Attach non-authorizing funded eligibility metadata to futures-plan results."""

from __future__ import annotations

from typing import Any

from apex.application.risk_approval import build_futures_plan_result
from apex.config import FuturesProductConfig, StrategyApprovalConfig
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import ProviderPolicyBinding, evaluate_funded_plan_