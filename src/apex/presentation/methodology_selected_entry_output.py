"""Final concise operator-facing renderer for Apex discovery output.

Full methodology diagnostics remain available in JSON. Normal text mode intentionally
shows only the decision, actionable geometry, material warnings, and concise reasoning.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from apex.presentation import OutputMode
from apex.presentation.discovery_output import (
    render_discovery_analysis as _render_operator_analysis,
)
from apex.presentation.discovery_output import render_discovery_scan as _render_operator_scan


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
    explain: bool = False,
) -> str:
    """Render the concise operator view; structured diagnostics stay in JSON."""

    rendered = _render_operator_analysis(payload, mode=mode)
    return _append_explanation(rendered, payload) if explain else rendered


def render_discovery_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render concise grouped scan results without internal diagnostic appendices."""

    rendered = _render_operator_scan(payload)
    return _append_explanation(rendered, payload) if explain else rendered


def _append_explanation(rendered: str, payload: Mapping[str, object]) -> str:
    diagnostics = {
        key: payload.get(key)
        for key in (
            "market_intelligence",
            "historical_edge",
            "timeframe_alignment",
            "strategy_routing",
            "candidate_ranking",
            "phase5_diagnostics",
            "screening",
        )
        if payload.get(key) is not None
    }
    if "results" in payload:
        diagnostics["results"] = payload.get("results")
    return f"{rendered}\n\nFull Diagnostics\n{json.dumps(diagnostics, indent=2, default=str)}"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
