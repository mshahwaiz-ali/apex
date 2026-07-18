"""Truthful public-output facade shared by scan and selected-symbol analysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from apex.application import public_output as _base
from apex.application.decision_analysis import DEFAULT_SCAN_DISPLAY_LIMIT
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_public_enrichment import methodology_public_enrichment


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Serialize one analysis and attach non-authoritative methodology metadata."""

    payload = _base.serialize_symbol_analysis(analysis)
    methodology = project_analysis_methodology(analysis)
    payload.update(methodology_public_enrichment(analysis, methodology))
    return payload


def serialize_scan_result(
    result: ScanResult,
    *,
    display_limit: int = DEFAULT_SCAN_DISPLAY_LIMIT,
    direction: str = "both",
) -> dict[str, Any]:
    """Serialize a scan while preserving base ranking and grouping behavior."""

    payload = _base.serialize_scan_result(
        result,
        display_limit=display_limit,
        direction=direction,
    )
    normalized_direction = direction.strip().lower()
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
    serialized = payload.get("results")
    if isinstance(serialized, list):
        for analysis, item in zip(displayed, serialized, strict=False):
            if not isinstance(item, dict):
                continue
            methodology = project_analysis_methodology(analysis)
            item.update(methodology_public_enrichment(analysis, methodology))

    completeness_counts: Counter[str] = Counter()
    authoritative_count = 0
    projected_count = 0
    for item in serialized if isinstance(serialized, list) else ():
        if not isinstance(item, Mapping):
            continue
        if item.get("methodology_projection_authoritative") is True:
            authoritative_count += 1
        else:
            projected_count += 1
        completeness = item.get("methodology_completeness")
        if isinstance(completeness, Mapping):
            unavailable = completeness.get("unavailable_fields")
            if isinstance(unavailable, list):
                completeness_counts.update(str(field) for field in unavailable)

    payload["methodology_authoritative_result_count"] = authoritative_count
    payload["methodology_projected_result_count"] = projected_count
    payload["methodology_unavailable_field_counts"] = dict(sorted(completeness_counts.items()))
    payload["methodology_coverage_interpretation"] = (
        "metadata coverage only; not ranking, trade quality, or win probability"
    )
    return payload


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]
