"""Trader-facing presentation for one current-setup futures simulation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_price,
    format_ratio,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_futures_simulation(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
