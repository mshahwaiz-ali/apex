"""Expose evidence-family independence without double-counting correlated signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_evidence_aggregation import aggregate_evidence_families
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceIndependenceSemantics:
    """Public interpretation of family support and independence-group diversity."""

    evidence_count: int
    family_count: int
    independence_group_count: int
    correlated_observation_count: int
    supporting_family_count: int
    contradicting_family_count: int
    strongest_support_family: str | None
    strongest_contradiction_family: str | None
    interpretation: str
    limitations: tuple[str, ...]


def derive_evidence_independence_semantics(
    methodology: MethodologySnapshot,
) -> EvidenceIndependenceSemantics:
    """Summarize independent evidence contribution by canonical family and group."""

    aggregates = aggregate_evidence_families(methodology.evidence)
    groups = {item.independence_group for item in methodology.evidence}
    correlated_count = max(0, len(methodology.evidence) - len(groups))
    supporting = tuple(item for item in aggregates if item.net_score > 0.0)
    contradicting = tuple(item for item in aggregates if item.net_score < 0.0)
    strongest_support = max(supporting, key=lambda item: item.net_score, default=None)
    strongest_contradiction = min(contradicting, key=lambda item: item.net_score, default=None)

    if not methodology.evidence:
        interpretation = "canonical evidence is unavailable; independence cannot be assessed"
    elif len(groups) == 1 and len(methodology.evidence) > 1:
        interpretation = (
            "multiple observations share one independence group and must not be counted as "
            "separate confirmations"
        )
    elif correlated_count:
        interpretation = (
            "some observations are correlated; family aggregation caps repeated group contribution"
        )
    else:
        interpretation = "all canonical observations use distinct independence groups"

    return EvidenceIndependenceSemantics(
        evidence_count=len(methodology.evidence),
        family_count=len(aggregates),
        independence_group_count=len(groups),
        correlated_observation_count=correlated_count,
        supporting_family_count=len(supporting),
        contradicting_family_count=len(contradicting),
        strongest_support_family=(
            None if strongest_support is None else strongest_support.family.value
        ),
        strongest_contradiction_family=(
            None if strongest_contradiction is None else strongest_contradiction.family.value
        ),
        interpretation=interpretation,
        limitations=(
            "independence groups are explicit metadata, not inferred statistical independence",
            "several indicators from one group do not become several independent confirmations",
            "family support scores are analytical aggregates, not probabilities",
            "evidence diversity cannot repair hard blockers or invalid execution geometry",
        ),
    )


def evidence_independence_semantics_payload(
    semantics: EvidenceIndependenceSemantics,
) -> dict[str, Any]:
    """Serialize evidence independence interpretation."""

    return {
        "evidence_count": semantics.evidence_count,
        "family_count": semantics.family_count,
        "independence_group_count": semantics.independence_group_count,
        "correlated_observation_count": semantics.correlated_observation_count,
        "supporting_family_count": semantics.supporting_family_count,
        "contradicting_family_count": semantics.contradicting_family_count,
        "strongest_support_family": semantics.strongest_support_family,
        "strongest_contradiction_family": semantics.strongest_contradiction_family,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "EvidenceIndependenceSemantics",
    "derive_evidence_independence_semantics",
    "evidence_independence_semantics_payload",
]
