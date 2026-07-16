"""Operator-facing presentation for validation, evidence, and readiness workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_percentage,
    format_ratio,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_validation(
    payload: Mapping[str, object],
    *,
    title: str = "Validation Readiness",
    mode: str | OutputMode = "text",
) -> str:
    """Render