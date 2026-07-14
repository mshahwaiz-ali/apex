"""Human-readable reporting for canonical trade-management plans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def format_trade_management_plan(plan: Mapping[str, Any]) -> str:
    """Render one serialized trade-management plan as operational instructions."""

    entry = _mapping(plan, "entry")
    protection = _mapping(plan, "initial_protection")
    targets = _sequence_of