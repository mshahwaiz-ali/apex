"""Final concise operator-facing renderer for Apex discovery output.

Full methodology diagnostics remain available in JSON. Normal text mode intentionally
shows only the decision, actionable geometry, material warnings, and concise reasoning.
"""

from __future__ import annotations

from collections.abc import Mapping

from apex.presentation import OutputMode
from apex.presentation.operator_output import render_analysis, render_scan


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
    explain: bool = False,
) -> str:
    """Render the concise operator view; structured diagnostics stay in JSON."""

    del mode
    return render_analysis(payload, explain=explain)


def render_discovery_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render concise grouped scan results without internal diagnostic appendices."""

    return render_scan(payload, explain=explain)


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
