"""Final concise operator-facing renderer for Apex discovery output.

Full methodology diagnostics remain available in JSON. Normal text mode intentionally
shows only the decision, actionable geometry, material warnings, and concise reasoning.
"""

from __future__ import annotations

from collections.abc import Mapping

from apex.presentation import OutputMode
from apex.presentation.compact_analysis_output import render_compact_analysis
from apex.presentation.compact_scan_output import render_compact_scan


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
    explain: bool = False,
) -> str:
    """Render selected-symbol analysis as compact sequential trade blocks."""

    del mode
    return render_compact_analysis(payload, explain=explain)


def render_discovery_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render confidence-ranked scan results with analyze-style trade cards."""

    return render_compact_scan(payload, explain=explain)


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
