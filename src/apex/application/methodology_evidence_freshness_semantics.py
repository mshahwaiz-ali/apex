"""Interpret methodology evidence freshness without inventing candle timestamps."""

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
    stale_evidence_count: int
    incomplete_data_blocked: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_evidence_freshness_semantics(
    methodology: MethodologySnapshot,
    *,
    stale_threshold: float = 0.5,
) -> EvidenceFreshnessSemantics:
    """Describe freshness only from explicit canonical evidence metadata."""

    freshness_values = tuple(item.freshness for item in methodology.evidence)
    stale_count = sum(value < stale_threshold for value in freshness_values)
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
    elif stale_count:
        interpretation = (
            "some canonical evidence is stale; freshness degradation remains visible and "
            "cannot be repaired by a higher score"
        )
    else:
        interpretation = "all canonical evidence freshness values meet the configured threshold"

    return EvidenceFreshnessSemantics(
        evidence_count=len(methodology.evidence),
        freshness_available=bool(freshness_values),
        minimum_freshness=min(freshness_values) if freshness_values else None,
        average_freshness=(
            sum(freshness_values) / len(freshness_values) if freshness_values else None
        ),
        stale_evidence_count=stale_count,
        incomplete_data_blocked=incomplete_data_blocked,
        interpretation=interpretation,
        limitations=(
            "freshness is a normalized evidence attribute, not an inferred candle timestamp",
            "missing freshness metadata must not be represented as fully fresh",
            "stale or incomplete data takes precedence over ranking and confidence labels",
            "closed-candle status requires explicit confirmation metadata",
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
        "stale_evidence_count": semantics.stale_evidence_count,
        "incomplete_data_blocked": semantics.incomplete_data_blocked,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "EvidenceFreshnessSemantics",
    "derive_evidence_freshness_semantics",
    "evidence_freshness_semantics_payload",
]
