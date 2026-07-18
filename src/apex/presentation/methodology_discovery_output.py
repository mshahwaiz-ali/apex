"""Methodology-aware text facade for discovery analysis and scan output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.discovery_output import (
    render_discovery_analysis as _render_base_analysis,
)
from apex.presentation.discovery_output import render_discovery_scan as _render_base_scan


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
