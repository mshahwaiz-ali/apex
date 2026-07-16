"""Persistence and policy-compatibility checks for funded provider limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

from apex.domain import AccountPolicy, AccountPolicyType
from apex.funded.provider_limits_registry import (
    FundedProviderLimitPreset,
    FundedProviderLimitsRegistry,
)

__all__ = [
    "load_funded_provider_limits_registry",
    "validate