"""Expose hard blockers and soft penalties as separate methodology decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import RejectionReason
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class RejectionSemantics:
    """Transparent rejection interpretation for one methodology snapshot."""

    hard_blockers: tuple[RejectionReason, ...]
    soft_penalties: tuple[RejectionReason, ...]
    total_soft_penalty: float
    execution_blocked: bool
    quality_reduced: bool
    interpretation: str


def derive_rejection_semantics(snapshot: MethodologySnapshot) -> RejectionSemantics:
    """Separate gates from quality deductions without inventing hidden rejection."""

    hard_blockers = snapshot.hard_blockers
    soft_penalties = snapshot.soft_penalties
    total_soft_penalty = sum(item.penalty for item in soft_penalties)
    if hard_blockers:
        interpretation = "execution is blocked by one or more explicit hard gates"
    elif soft_penalties:
        interpretation = (
            "execution is not hard-blocked; visible soft penalties reduce analytical quality"
        )
    else:
        interpretation = "no explicit methodology rejection or soft penalty is present"
    return RejectionSemantics(
        hard_blockers=hard_blockers,
        soft_penalties=soft_penalties,
        total_soft_penalty=total_soft_penalty,
        execution_blocked=bool(hard_blockers),
        quality_reduced=bool(soft_penalties),
        interpretation=interpretation,
    )


def rejection_semantics_payload(semantics: RejectionSemantics) -> dict[str, Any]:
    """Serialize transparent gates and penalties for public output."""

    return {
        "execution_blocked": semantics.execution_blocked,
        "quality_reduced": semantics.quality_reduced,
        "hard_blocker_count": len(semantics.hard_blockers),
        "soft_penalty_count": len(semantics.soft_penalties),
        "total_soft_penalty": semantics.total_soft_penalty,
        "interpretation": semantics.interpretation,
        "hard_blockers": [_reason_payload(item) for item in semantics.hard_blockers],
        "soft_penalties": [_reason_payload(item) for item in semantics.soft_penalties],
    }


def _reason_payload(reason: RejectionReason) -> dict[str, Any]:
    return {
        "code": reason.code.value,
        "severity": reason.severity.value,
        "reason": reason.reason,
        "penalty": reason.penalty,
    }


__all__ = [
    "RejectionSemantics",
    "derive_rejection_semantics",
    "rejection_semantics_payload",
]
