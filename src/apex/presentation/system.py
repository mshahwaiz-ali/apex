"""Trader-facing presentation for Apex system and market-data commands."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_price,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render