"""Integration tests for combined risk-mode and account-policy approval."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from apex.application import build_futures_plan_result
from apex.config import load_account_policies_config
from apex.domain import AccountPolicyState, FuturesAccountInput, RiskMode
from apex.risk import (
    ActionableEntry,
    LeverageRange,
    ManagementPolicy,
    ManagementPolicyType,
    PositionSize,
