"""Interpret canonical contradictions without treating every disagreement as invalidation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ContradictionSemantics:
    """Public interpretation of contradiction count, severity, and execution effect."""

    contradiction_count: int
    maximum_severity: float | None
    average_severity: float | None
    high_severity_count: int
    affected_families: tuple[str, ...]
    execution_blocked: bool
    invalidation_present: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_contradiction_semantics(
    methodology: MethodologySnapshot,
    *,
    high_severity_threshold: float = 0.75,
) -> ContradictionSemantics:
    """Distinguish contradictory evidence from explicit hard-blocker invalidation."""

    contradictions = methodology.contradictions
    severities = tuple(item.severity for item in contradictions)
    high_count = sum(value >= high_severity_threshold for value in severities)
    families = tuple(sorted({item.family.value for item in contradictions}))
    execution_blocked = bool(methodology.hard_blockers)
    invalidation_present = any(
        item.code.value in {"structurally_invalidated", "pattern_failed"}
        for item in methodology.hard_blockers
    )

    if not contradictions:
        interpretation = "no canonical contradictions are recorded"
    elif invalidation_present:
        interpretation = (
            "contradictory evidence accompanies explicit structural invalidation or pattern failure"
        )
    elif execution_blocked:
        interpretation = "contradictions are present alongside a separate methodology hard blocker"
    elif high_count:
        interpretation = (
            "high-severity contradictions materially reduce analytical quality but do not "
            "independently invalidate the setup"
        )
    else:
        interpretation = (
            "contradictions weaken confidence and ranking while remaining distinct from "
            "hard rejection"
        )

    return ContradictionSemantics(
        contradiction_count=len(contradictions),
        maximum_severity=max(severities) if severities else None,
        average_severity=(sum(severities) / len(severities) if severities else None),
        high_severity_count=high_count,
        affected_families=families,
        execution_blocked=execution_blocked,
        invalidation_present=invalidation_present,
        interpretation=interpretation,
        limitations=(
            "contradiction severity is analytical weight, not failure probability",
            "contradictions reduce confidence but only explicit hard blockers prevent execution",
            "several contradictions from one evidence family are not independent confirmations",
            "a high score must not conceal material contradictory evidence",
        ),
    )


def contradiction_semantics_payload(
    semantics: ContradictionSemantics,
) -> dict[str, Any]:
    """Serialize contradiction interpretation for public output."""

    return {
        "contradiction_count": semantics.contradiction_count,
        "maximum_severity": semantics.maximum_severity,
        "average_severity": semantics.average_severity,
        "high_severity_count": semantics.high_severity_count,
        "affected_families": list(semantics.affected_families),
        "execution_blocked": semantics.execution_blocked,
        "invalidation_present": semantics.invalidation_present,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ContradictionSemantics",
    "contradiction_semantics_payload",
    "derive_contradiction_semantics",
]
