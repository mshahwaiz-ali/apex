"""Export machine-readable schemas for funded futures-plan workflows."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import TypeAdapter

from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import FundedPlanEligibility, ProviderPolicyBinding
from apex.risk import RiskApprovedSetup

__all__ = ["build_funded_plan_schema_bundle