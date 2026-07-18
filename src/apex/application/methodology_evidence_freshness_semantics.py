"""Interpret methodology evidence freshness from normalized and timestamped sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_source_data_contracts import (
    EvidenceSourceReference,
    SourceCandleMetadata,
)


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessSemantics:
    """Public interpretation of canonical evidence freshness metadata."""

    evidence_count: int
    freshness_available: bool
    minimum_freshness: float | None
    average_freshness: float | None
    source_metadata_count: int
    linked_evidence_count: int
    minimum_source_age_seconds: float | None
    maximum_source_age_seconds: float | None
    maximum_source_age_intervals: float | None
    threshold_configured: bool
    stale_evidence_count: int | None
    incomplete_data_blocked: bool
    timestamp_recency_proven: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_evidence_freshness_semantics(
    methodology: MethodologySnapshot,
    source_candles: tuple[SourceCandleMetadata, ...] = (),
    source_references: tuple[EvidenceSourceReference, ...] = (),
) -> EvidenceFreshnessSemantics:
    """Describe timestamp age without inventing a universal staleness boundary."""

    _validate_source_links(methodology, source_candles, source_references)
    freshness_values = tuple(item.freshness for item in methodology.evidence)
    incomplete_data_blocked = any(
        item.code.value == "stale_or_incomplete_data" for item in methodology.hard_blockers
    )
    linked_source_ids = {item.source_id for item in source_references}
    linked_sources = tuple(item for item in source_candles if item.source_id in linked_source_ids)
    source_ages = tuple(item.age_seconds for item in linked_sources)
    interval_ages = tuple(
        item.age_intervals for item in linked_sources if item.age_intervals is not None
    )
    timestamp_recency_proven = bool(linked_sources)

    if not freshness_values and not linked_sources:
        interpretation = (
            "canonical evidence freshness and source timestamps are unavailable; recency and "
            "closure state must not be inferred"
        )
    elif incomplete_data_blocked:
        interpretation = "stale or incomplete data is an explicit hard execution blocker"
    elif linked_sources:
        interpretation = (
            "physical source ages are derived from recorded close and observation timestamps; "
            "no source is classified stale without a configured strategy-specific threshold"
        )
    else:
        interpretation = (
            "normalized freshness values are available, but no source timestamp or configured "
            "staleness threshold proves that any item is current or stale"
        )

    limitations = [
        "no universal normalized-value cutoff is treated as a staleness boundary",
        "stale or incomplete data blockers take precedence over ranking and confidence",
        "physical candle closure and source age are separate from normalized freshness scores",
    ]
    if not linked_sources:
        limitations.append("missing evidence-to-source links prevent timestamp-based recency proof")
    if not interval_ages:
        limitations.append(
            "source age cannot be normalized by timeframe without explicit interval duration"
        )

    return EvidenceFreshnessSemantics(
        evidence_count=len(methodology.evidence),
        freshness_available=bool(freshness_values),
        minimum_freshness=min(freshness_values) if freshness_values else None,
        average_freshness=(
            sum(freshness_values) / len(freshness_values) if freshness_values else None
        ),
        source_metadata_count=len(source_candles),
        linked_evidence_count=len(source_references),
        minimum_source_age_seconds=min(source_ages) if source_ages else None,
        maximum_source_age_seconds=max(source_ages) if source_ages else None,
        maximum_source_age_intervals=max(interval_ages) if interval_ages else None,
        threshold_configured=False,
        stale_evidence_count=None,
        incomplete_data_blocked=incomplete_data_blocked,
        timestamp_recency_proven=timestamp_recency_proven,
        interpretation=interpretation,
        limitations=tuple(limitations),
    )


def evidence_freshness_semantics_payload(
    semantics: EvidenceFreshnessSemantics,
) -> dict[str, Any]:
    """Serialize evidence freshness interpretation."""

    return {
        "evidence_count": semantics.evidence_count,
        "freshness_available": semantics.freshness_available,
        "minimum_freshness": semantics.minimum_freshness,
        "average_freshness": semantics.average_freshness,
        "source_metadata_count": semantics.source_metadata_count,
        "linked_evidence_count": semantics.linked_evidence_count,
        "minimum_source_age_seconds": semantics.minimum_source_age_seconds,
        "maximum_source_age_seconds": semantics.maximum_source_age_seconds,
        "maximum_source_age_intervals": semantics.maximum_source_age_intervals,
        "threshold_configured": semantics.threshold_configured,
        "stale_evidence_count": semantics.stale_evidence_count,
        "incomplete_data_blocked": semantics.incomplete_data_blocked,
        "timestamp_recency_proven": semantics.timestamp_recency_proven,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _validate_source_links(
    methodology: MethodologySnapshot,
    sources: tuple[SourceCandleMetadata, ...],
    references: tuple[EvidenceSourceReference, ...],
) -> None:
    source_ids = [item.source_id for item in sources]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("source candle identifiers must be unique")
    reference_keys = [(item.evidence_index, item.source_id) for item in references]
    if len(set(reference_keys)) != len(reference_keys):
        raise ValueError("evidence source references must be unique")
    known_ids = set(source_ids)
    if any(item.source_id not in known_ids for item in references):
        raise ValueError("evidence source reference must identify a recorded source candle")
    if any(item.evidence_index >= len(methodology.evidence) for item in references):
        raise ValueError("evidence source reference index is outside canonical evidence")


__all__ = [
    "EvidenceFreshnessSemantics",
    "derive_evidence_freshness_semantics",
    "evidence_freshness_semantics_payload",
]
