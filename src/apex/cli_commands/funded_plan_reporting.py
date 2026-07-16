"""Read-only reporting for funded futures-plan payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import typer

from apex.funded import FundedPlanEligibility


__all__ = ["register_funded_plan_reporting_commands"]


def register_funded_plan_reporting_commands(app: typer.Typer) -> None:
    """Register funded-plan reporting without