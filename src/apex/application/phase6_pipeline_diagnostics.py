"""Stable Phase 6 risk-decision diagnostics for futures scan runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import SymbolAnalysis
from apex.risk import RiskDecision


@dataclass(frozen=True, slots=True)
class Phase6DiagnosticSummary:
    """Deterministic run-level Phase 6 approval and rejection statistics."""

    analyses_observed: int
    approved: int
    rejected: int
    rejection_code_counts: Mapping[str, int]
    rejection_counts_by_scanner_category: Mapping[str, Mapping[str, int]]
    rejection_counts_by_strategy: Mapping[str, Mapping[str, int]]
    approved_counts_by_strategy: Mapping[str, int