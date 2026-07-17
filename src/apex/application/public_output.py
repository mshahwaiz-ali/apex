"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from typing import Any

from apex.application import decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult


def serialize_symbol_analysis(analysis: _decision.SymbolAnalysis) -> dict[str, Any]:
    """Return one discovery result without legacy entry-state overlays."""

    payload = _decision.serialize_symbol_analysis(analysis)
    payload.pop("near_current_entry", None)
    payload.pop("precision_entry", None)

    setup = payload.get("setup")
    if not isinstance(setup, dict):
        payload["entry_status"] = None
        payload["strategy"] = None
        payload["confidence_score"] = None
        payload["decision_reason_code"] = "NO_TRADE"
        return payload

    status = setup.get("entry_status")
    payload["entry_status"] = status
    payload["strategy"] = setup.get("strategy")
    payload["confidence_score"] = setup.get("confidence_score")
    payload["decision_reason_code"] = status
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    """Return ranked scan output with canonical actionability counts."""

    displayed = tuple(result.analyses[: _decision.DEFAULT_SCAN_DISPLAY_LIMIT])
    serialized = [serialize_symbol_analysis(item) for item in displayed]
    actionable = [item for item in serialized if item.get("setup") is not None]
    status_counts = Counter(
        str(item["entry_status"])
        for item in actionable
        if item.get("entry_status") is not None
    )
    long_count = sum(item.get("decision") == "LONG" for item in actionable)
    short_count = sum(item.get("decision") == "SHORT" for item in actionable)
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": actionable[0] if actionable else None,
        "results": serialized,
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(serialized),
        "display_limit": _decision.DEFAULT_SCAN_DISPLAY_LIMIT,
        "actionable_count": len(actionable),
        "long_candidate_count": long_count,
        "short_candidate_count": short_count,
        "status_counts": dict(sorted(status_counts.items())),
        "failures": dict(result.failures),
    }


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]
