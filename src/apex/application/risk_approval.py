"""Combine risk-mode limits and account-policy permissions for futures plans."""

from __future__ import annotations

from apex.application.futures_plan import (
    FuturesPlanSafetyError as FuturesPlanSafetyError,
)
from apex.application.futures_plan import build_futures_plan as _build_futures_plan
from apex.config import FuturesProductConfig, RiskModeDefaults, load_futures_product_config
from apex.domain import (
    AccountPolicy,
    AccountPolicyDecision,
    AccountPolicyState,
    FuturesAccountInput