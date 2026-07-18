"""Add methodology indexing metadata to persisted analysis records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from apex.application.analysis_records import build_analysis_record as _build_base_record


def build_analysis_record(
    payload: Mapping[str, Any],
    *,
    provider: str = "configured-provider",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the base record and expose methodology provenance for indexing.

    The complete serialized payload remains authoritative and unchanged. These
    top-level fields are convenience metadata only and do not alter analysis IDs,
    content hashes, ranking, or trade-selection behavior.
    """

    record = _build_base_record(
        payload,
        provider=provider,
        recorded_at=recorded_at,
    )
    source_type = record.get("source_type")
    if source_type == "scan":
        record.update(_scan_methodology_metadata(payload))
    else:
        record.update(_analysis_methodology_metadata(payload))
    return record


def _analysis_methodology_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    authoritative = payload.get("methodology_projection_authoritative")
    completeness = _mapping(payload.get("methodology_completeness"))
    maturity = _mapping(payload.get("methodology_setup_maturity"))
    return {
        "methodology_authority": _authority(authoritative),
        "methodology_maturity": maturity.get("maturity"),
        "methodology_execution_ready": payload.get("execution_ready"),
        "methodology_available_field_count": completeness.get("available_field_count"),
        "methodology_field_count": completeness.get("field_count"),
        "methodology_complete": completeness.get("complete"),
    }


def _scan_methodology_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "methodology_authoritative_result_count": payload.get(
            "methodology_authoritative_result_count"
        ),
        "methodology_projected_result_count": payload.get("methodology_projected_result_count"),
        "methodology_unavailable_field_counts": payload.get("methodology_unavailable_field_counts"),
        "methodology_coverage_interpretation": payload.get("methodology_coverage_interpretation"),
    }


def _authority(value: object) -> str:
    if value is True:
        return "native"
    if value is False:
        return "projected"
    return "unavailable"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


__all__ = ["build_analysis_record"]
