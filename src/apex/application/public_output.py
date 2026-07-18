"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

import apex.application.decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_snapshot import methodology_snapshot_payload

_LEGACY_PUBLIC_KEYS = frozenset({"near_miss_state"})
_ACTIONABLE_STATUSES = frozenset({"READY_NOW", "AGGRESSIVE_NOW"})
_DEVELOPING_STATUSES = frozenset({"PULLBACK_PREFERRED", "WATCH_NEAR_ENTRY"})
_UNAVAILABLE_STATUSES = frozenset({"LATE_OR_CHASING", "INVALIDATED"})


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Return one discovery result without legacy entry-state overlays."""

    payload = _without_legacy_keys(_decision.serialize_symbol_analysis(analysis))
    payload["methodology"] = methodology_snapshot_payload(
        project_analysis_methodology(analysis)
    )
    setup = payload.get("setup")
    if not isinstance(setup, dict):
        payload["entry_status"] = None
        payload["strategy"] = None
        payload["confidence_score"] = None
        payload["decision_reason_code"] = "NO_TRADE"
        payload["result_group"] = "no_trade"
        return cast(dict[str, Any], payload)

    status = setup.get("entry_status")
    payload["entry_status"] = status
    payload["strategy"] = setup.get("strategy")
    payload["confidence_score"] = setup.get("confidence_score")
    payload["decision_reason_code"] = status
    payload["result_group"] = _result_group(status)
    return cast(dict[str, Any], payload)


def serialize_scan_result(
    result: ScanResult,
    *,
    display_limit: int = _decision.DEFAULT_SCAN_DISPLAY_LIMIT,
    direction: str = "both",
) -> dict[str, Any]:
    """Return ranked scan output grouped by canonical actionability."""

    if display_limit < 1:
        raise ValueError("display limit must be positive")
    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"long", "short", "both"}:
        raise ValueError("direction must be one of: long, short, both")

    ranked = (
        result.analyses
        if normalized_direction == "both"
        else tuple(
            item
            for item in result.analyses
            if item.assessment.setup is not None
            and item.assessment.setup.direction.value == normalized_direction
        )
    )
    displayed = tuple(ranked[:display_limit])
    serialized = [serialize_symbol_analysis(item) for item in displayed]
    actionable = [item for item in serialized if item.get("result_group") == "actionable"]
    developing = [item for item in serialized if item.get("result_group") == "developing"]
    unavailable = [item for item in serialized if item.get("result_group") == "unavailable"]
    no_trade = [item for item in serialized if item.get("result_group") == "no_trade"]
    selected = [item for item in serialized if item.get("setup") is not None]
    status_counts = Counter(
        str(item["entry_status"])
        for item in selected
        if item.get("entry_status") is not None
    )
    long_count = sum(item.get("decision") == "LONG" for item in selected)
    short_count = sum(item.get("decision") == "SHORT" for item in selected)
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": selected[0] if selected else None,
        "actionable_setups": actionable,
        "developing_setups": developing,
        "unavailable_setups": unavailable,
        "no_trade_results": no_trade,
        "results": serialized,
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(serialized),
        "display_limit": display_limit,
        "direction_filter": normalized_direction,
        "selected_setup_count": len(selected),
        "actionable_count": len(actionable),
        "developing_count": len(developing),
        "unavailable_count": len(unavailable),
        "no_trade_count": len(no_trade),
        "long_candidate_count": long_count,
        "short_candidate_count": short_count,
        "status_counts": dict(sorted(status_counts.items())),
        "failures": dict(result.failures),
    }


def _result_group(status: object) -> str:
    normalized = str(status) if status is not None else ""
    if normalized in _ACTIONABLE_STATUSES:
        return "actionable"
    if normalized in _DEVELOPING_STATUSES:
        return "developing"
    if normalized in _UNAVAILABLE_STATUSES:
        return "unavailable"
    return "no_trade"


def _without_legacy_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_legacy_keys(item)
            for key, item in value.items()
            if str(key) not in _LEGACY_PUBLIC_KEYS
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_without_legacy_keys(item) for item in value]
    return value


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]