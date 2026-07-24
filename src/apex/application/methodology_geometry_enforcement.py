"""Guarded geometry enforcement before candidate scoring and selection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from apex.application.methodology_candidate_geometry_safety import (
    CandidateGeometrySafetyAudit,
)
from apex.application.methodology_candidate_routing import (
    MethodologyCandidateRoutingResult,
)
from apex.application.methodology_geometry_safety import (
    GeometrySafetyAssessment,
    GeometrySafetyState,
)
from apex.strategies.analysis import (
    CandidateActionability,
    StrategyAnalysisResult,
    SuppressedStrategyCandidate,
)
from apex.strategies.candidate_identity import candidate_identities


def _effective_assessment(
    audit: CandidateGeometrySafetyAudit,
) -> GeometrySafetyAssessment | None:
    "Prefer measured geometry while preserving lightweight audit compatibility."

    measured = getattr(audit, "measured_assessment", None)
    return measured if measured is not None else audit.assessment


class GeometrySafetyGateMode(StrEnum):
    """Rollout mode for candidate geometry enforcement."""

    SHADOW = "shadow"
    ENFORCE = "enforce"


class GeometrySafetyEnforcementUnavailableError(RuntimeError):
    """Raised when enforcement is requested without complete coverage."""


@dataclass(frozen=True, slots=True)
class GeometrySafetyEnforcementResult:
    """Geometry gate result passed to scoring and portfolio selection."""

    analysis: StrategyAnalysisResult
    mode: GeometrySafetyGateMode
    input_candidate_count: int
    rejected_candidate_count: int
    rejected_candidate_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.input_candidate_count < 0 or self.rejected_candidate_count < 0:
            raise ValueError("geometry enforcement counts cannot be negative")
        if self.rejected_candidate_count != len(self.rejected_candidate_ids):
            raise ValueError("rejected geometry count must match identities")
        if (
            len(self.analysis.candidates) + self.rejected_candidate_count
            != self.input_candidate_count
        ):
            raise ValueError("geometry enforcement candidate counts must balance")
        if not self.reason_codes:
            raise ValueError("geometry enforcement requires reason codes")


def apply_geometry_safety_enforcement(
    routing: MethodologyCandidateRoutingResult,
    *,
    mode: GeometrySafetyGateMode | str = GeometrySafetyGateMode.SHADOW,
) -> GeometrySafetyEnforcementResult:
    """Reject geometry failures only with complete retained-candidate coverage."""

    normalized_mode = GeometrySafetyGateMode(mode)
    analysis = routing.analysis
    if normalized_mode is GeometrySafetyGateMode.SHADOW:
        return GeometrySafetyEnforcementResult(
            analysis=analysis,
            mode=normalized_mode,
            input_candidate_count=len(analysis.candidates),
            rejected_candidate_count=0,
            rejected_candidate_ids=(),
            reason_codes=("GEOMETRY_SAFETY_SHADOW",),
        )

    identities = candidate_identities(analysis.candidates)
    audit_by_id = {audit.candidate_id: audit for audit in routing.geometry_safety_audits}
    retained_audits: list[CandidateGeometrySafetyAudit] = []
    missing_audits: list[str] = []
    incomplete_audits: list[str] = []

    for candidate_id in identities:
        audit = audit_by_id.get(candidate_id)
        if audit is None:
            missing_audits.append(candidate_id)
            continue
        retained_audits.append(audit)
        effective_assessment = _effective_assessment(audit)
        if (
            effective_assessment is None
            or effective_assessment.state is GeometrySafetyState.INCOMPLETE
        ):
            incomplete_audits.append(candidate_id)

    if missing_audits or incomplete_audits:
        details: list[str] = []
        if missing_audits:
            details.append(f"missing audits: {', '.join(missing_audits)}")
        if incomplete_audits:
            details.append(f"incomplete audits: {', '.join(incomplete_audits)}")
        raise GeometrySafetyEnforcementUnavailableError(
            "geometry enforcement requires complete retained-candidate coverage; "
            + "; ".join(details)
        )

    rejected_ids_list: list[str] = []
    for audit in retained_audits:
        assessment = _effective_assessment(audit)
        if assessment is not None and assessment.state is GeometrySafetyState.REJECT:
            rejected_ids_list.append(audit.candidate_id)
    rejected_ids = tuple(rejected_ids_list)
    rejected_set = set(rejected_ids)
    status_by_object = {
        id(item.candidate): item.status for item in analysis.candidate_actionability
    }
    retained_candidates = tuple(
        candidate
        for candidate, candidate_id in zip(analysis.candidates, identities, strict=True)
        if candidate_id not in rejected_set
    )
    retained_actionability = tuple(
        CandidateActionability(
            candidate=candidate,
            status=status_by_object[id(candidate)],
        )
        for candidate in retained_candidates
    )

    candidate_by_id = dict(zip(identities, analysis.candidates, strict=True))
    rejected_suppressed: list[SuppressedStrategyCandidate] = []
    for audit in retained_audits:
        assessment = _effective_assessment(audit)
        if assessment is None or assessment.state is not GeometrySafetyState.REJECT:
            continue
        candidate = candidate_by_id[audit.candidate_id]
        rejected_suppressed.append(
            SuppressedStrategyCandidate(
                candidate=candidate,
                candidate_id=audit.candidate_id,
                entry_status=status_by_object[id(candidate)],
                reason_codes=tuple(code.value for code in assessment.rejection_codes),
                reasons=assessment.reasons,
                suppression_stage="geometry_safety",
            )
        )

    updated = replace(
        analysis,
        candidates=retained_candidates,
        candidate_actionability=retained_actionability,
        suppressed_candidates=(
            *analysis.suppressed_candidates,
            *rejected_suppressed,
        ),
    )
    return GeometrySafetyEnforcementResult(
        analysis=updated,
        mode=normalized_mode,
        input_candidate_count=len(analysis.candidates),
        rejected_candidate_count=len(rejected_ids),
        rejected_candidate_ids=rejected_ids,
        reason_codes=(
            "GEOMETRY_SAFETY_ENFORCED"
            if rejected_ids
            else "GEOMETRY_SAFETY_ENFORCED_NO_REJECTIONS",
        ),
    )


def geometry_safety_enforcement_payload(
    result: GeometrySafetyEnforcementResult,
) -> dict[str, object]:
    """Serialize guarded geometry enforcement diagnostics."""

    return {
        "mode": result.mode.value,
        "input_candidate_count": result.input_candidate_count,
        "retained_candidate_count": len(result.analysis.candidates),
        "rejected_candidate_count": result.rejected_candidate_count,
        "rejected_candidate_ids": list(result.rejected_candidate_ids),
        "reason_codes": list(result.reason_codes),
    }


__all__ = [
    "GeometrySafetyEnforcementResult",
    "GeometrySafetyEnforcementUnavailableError",
    "GeometrySafetyGateMode",
    "apply_geometry_safety_enforcement",
    "geometry_safety_enforcement_payload",
]
