"""Professional terminal presentation for paper-trading operations."""

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
    render_fields