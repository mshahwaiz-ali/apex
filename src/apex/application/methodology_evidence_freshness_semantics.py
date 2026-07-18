"""Interpret methodology evidence freshness without inventing recency thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessSemantics:
    """Public interpretation of canonical evidence freshness metadata."""

    evidence_count: int
    freshness_available: bool
    minimum_freshness: float | None
    average_freshness: float | None
    threshold_configured: bool
    stale_evidence_count: int | None
    incomplete_data_blocked: bool
    timestamp_recency_proven: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_evidence_freshness_semantics(
    methodology: MethodologySnapshot,
) -> EvidenceFreshnessSemantics:
    """Describe normalized freshness without converting it into unsupported staleness."""

    freshness_values = tuple(item.freshness for item in methodology.evidence)
    incomplete_data_blocked = any(
        item.code.value == "stale_or_incomplete_data" for item in methodology.hard_blockers
    )
    if not freshness_values:
        interpretation = (
            "canonical evidence freshness is unavailable; candle recency and closure state "
            "must not be inferred"
        )
    elif incomplete_data_blocked:
        interpretation = "stale or incomplete data is an explicit hard execution blocker"
    else:
        interpretation = (
            "normalized freshness values are available, but no configured staleness threshold "
            "or source timestamp proves that any item is current or stale"
        )

    return EvidenceFreshnessSemantics(
        evidence_count=len(methodology.evidence),
        freshness_available=bool(freshness_values),
        minimum_freshness=min(freshness_values) if freshness_values else None,
        average_freshness=(
            sum(freshness_values) / len(freshness_values) if freshness_values else None
        ),
        threshold_configured=False,
        stale_evidence_count=None,
        incomplete_data_blocked=incomplete_data_blocked,
        timestamp_recency_proven=False,
        interpretation=interpretation,
        limitations=(
            "freshness is a normalized evidence attribute, not a source timestamp",
            "no universal normalized-value cutoff is treated as a staleness boundary",
            "missing freshness metadata must not be represented as fully fresh",
            "stale or incomplete data blockers take precedence over ranking and confidence",
            "closed-candle status requires explicit physical candle-state metadata",
        ),
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
        "threshold_configured": semantics.threshold_configured,
        "stale_evidence_count": semantics.stale_evidence_count,
        "incomplete_data_blocked": semantics.incomplete_data_blocked,
        "timestamp_recency_proven": semantics.timestamp_recency_proven,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "EvidenceFreshnessSemantics",
    "derive_evidence_freshness_semantics",
    "evidence_freshness_semantics_payload",
]
