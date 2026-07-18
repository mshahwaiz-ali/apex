"""Build truthful methodology metadata for public discovery output."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_confidence_semantics import (
    confidence_semantics_payload,
    derive_confidence_semantics,
)
from apex.application.methodology_geometry_projection import project_setup_geometry
from apex.application.methodology_provenance import (
    derive_methodology_provenance,
    methodology_completeness_payload,
    methodology_provenance_payload,
)
from apex.application.methodology_rejection_semantics import (
    derive_rejection_semantics,
    rejection_semantics_payload,
)
from apex.application.methodology_score_semantics import (
    derive_score_semantics,
    score_semantics_payload,
)
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_target_horizon_semantics import (
    derive_target_horizon_semantics,
    target_horizon_semantics_payload,
)


def methodology_public_enrichment(
    analysis: SymbolAnalysis,
    projected: MethodologySnapshot,
) -> dict[str, Any]:
    """Return transparent projection, score, target, and rejection semantics.

    The enrichment remains separate from the canonical methodology snapshot. It
    reports field origin and compatibility geometry without allowing projected or
    unavailable values to masquerade as native evidence, calibrated probability,
    hidden rejection, score-authorized execution, or a universal target horizon.
    """

    provenance = derive_methodology_provenance(
        stored_methodology=analysis.methodology,
        projected=projected,
    )
    setup = analysis.assessment.setup
    confidence = derive_confidence_semantics(projected.confidence)
    rejections = derive_rejection_semantics(projected)
    score = derive_score_semantics(setup, projected)
    target_horizon = derive_target_horizon_semantics(projected)
    return {
        "methodology_provenance": methodology_provenance_payload(provenance),
        "methodology_completeness": methodology_completeness_payload(provenance),
        "methodology_compatibility_geometry": (
            None if setup is None else project_setup_geometry(setup)
        ),
        "methodology_confidence_semantics": confidence_semantics_payload(confidence),
        "methodology_rejection_semantics": rejection_semantics_payload(rejections),
        "methodology_score_semantics": score_semantics_payload(score),
        "methodology_target_horizon_semantics": target_horizon_semantics_payload(
            target_horizon
        ),
        "methodology_projection_authoritative": analysis.methodology is not None,
        "methodology_projection_notice": _projection_notice(analysis),
    }


def _projection_notice(analysis: SymbolAnalysis) -> str:
    if analysis.methodology is not None:
        return "native methodology values remain authoritative"
    if analysis.assessment.setup is None:
        return "no selected setup exists; unavailable methodology fields remain deferred"
    return (
        "compatibility values were projected from the selected legacy setup; "
        "unavailable fields were not fabricated"
    )


__all__ = ["methodology_public_enrichment"]
