"""Tests for trader-facing spot workflow presentation."""

from __future__ import annotations

from apex.presentation.spot import render_spot_analysis, render_spot_plan, render_spot_scan


def _planning_payload() -> dict[str, object]:
    return {
        "entry_plan": {"primary_entry_price": 100.0, "maximum_entry_price": 102.0},
        "stop_plan": {"stop_price": 94.0, "risk_percentage": 6.0