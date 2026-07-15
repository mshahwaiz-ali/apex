"""Stable diagnostic aggregation for futures scans and paper pipelines."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.phase5_pipeline_diagnostics import (
    build_phase5_diagnostic_summary,
    phase5_analysis_payload,
)
from apex.application.phase6_pipeline_diagnostics