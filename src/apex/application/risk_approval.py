"""Combine strategy quality, risk-mode limits, and account-policy permissions."""

from __future__ import annotations

from pathlib import Path

from apex.application.futures_plan import (
    FuturesPlanSafetyError as FuturesPlanSafetyError,
)
from apex.application.futures_plan import build_futures_plan as _build_futures_plan
from apex.application.trade_management import build_trade_management_plan
from apex.config import (
    FuturesProductConfig,
    RiskModeDefaults,
    StrategyApprovalConfig,
    load_futures_product_config,
    load_strategy_approval_config,
)
from apex.domain import (
    AccountPolicy,
    AccountPolicyDecision,
    AccountPolicyState,
    EntryPlan,
    FuturesAccountInput,
    FuturesDirection,