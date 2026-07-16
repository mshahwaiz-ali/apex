"""Trader-facing futures analysis presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_amount,
    format_percentage,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    humanize_warnings,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_futures_analysis(
