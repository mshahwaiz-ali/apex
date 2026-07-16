"""Generate non-authorizing funded futures-plan payloads from validated JSON inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar, cast

import typer
from pydantic import BaseModel

from apex.application import build_funded_futures_plan_result
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import ProviderPolicyBinding
from apex.risk import RiskApprovedSetup

__all__ = ["register_funded_plan_generation