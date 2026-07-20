"""Trade-first terminal output for Apex scan and selected-symbol analysis."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from apex.presentation import (
    UNAVAILABLE,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)
from apex.presentation.cli_information_architecture import (
    canonical_actionability_label,
