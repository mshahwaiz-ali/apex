"""Stable diagnostic aggregation for the combined futures paper pipeline."""

from __future__ import annotations

from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis


def build_futures_pipeline_diagnostics(scan: ScanResult) -> dict[str, Any]:
    """Return scanner and per-analysis Phase 4 diagnostics for persisted audit logs."""

    analyses = {
        _analysis_key(analysis): _analysis_diagnostics(analysis)
        for analysis in scan.analyses
    }
    return {
        "scan_analysis_count": len(scan.analyses),
        "scanner_failure_count": len(scan.failures),
        "scanner_failures": dict(scan.failures),
        "phase4_analyses": analyses,
    }


def _analysis_key(analysis: SymbolAnalysis) -> str:
    return f"{analysis.symbol}:{analysis.scanner_type.value}"


def _analysis_diagnostics(analysis: SymbolAnalysis) -> dict[str, Any]:
    routing = analysis.strategy_routing
    return {
        "symbol": analysis.symbol,
        "scanner_type": analysis.scanner_type.value,
        "candidate_count": analysis.candidate_count,
        "decision_regime": routing.get("decision_regime"),
        "higher_timeframe_breakout": bool(routing.get("higher_timeframe_breakout", False)),
        "near_miss_state_counts": dict(routing.get("near_miss_state_counts", {})),
        "phase4_strategy_diagnostics": dict(
            routing.get("phase4_strategy_diagnostics", {})
        ),
        "routed_eligible_strategies": list(
            routing.get("routed_eligible_strategies", [])
        ),
        "skipped_strategies": dict(routing.get("skipped_strategies", {})),
    }
