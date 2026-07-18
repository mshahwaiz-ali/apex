"""Final concise operator-facing renderer for Apex discovery output.

Full methodology diagnostics remain available in JSON. Normal text mode intentionally
shows only the decision, actionable geometry, material warnings, and concise reasoning.
"""

from __future__ import annotations

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
) -> str:
    """Render the concise operator view; structured diagnostics stay in JSON."""

    return _render_operator_analysis(payload, mode=mode)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render concise grouped scan results without internal diagnostic appendices."""

    return _render_operator_scan(payload)


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
