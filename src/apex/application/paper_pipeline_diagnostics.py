"""Stable diagnostic aggregation for the combined futures paper pipeline."""

from __future__ import annotations

from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis


def build_futures_pipeline_diagnostics(scan: ScanResult) -> dict[str, Any]:
    """Return scanner and per-analysis Phase 4 diagnostics for persisted audit logs."""

    analyses = {
        _analysis_key(analysis): _analysis_d