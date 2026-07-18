"""Build truthful methodology metadata for public discovery output."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_geometry_projection import project_setup_geometry
from apex.application.methodology_provenance import (
    derive_methodology_provenance,
    methodology_completeness_payload,
    methodology_provenance_payload,
)
from apex.application.methodology_snapshot import MethodologySnapshot


def methodology_public_enrichment(
    analysis: SymbolAnalysis,
    projected: MethodologySnapshot,
) -> dict[str, Any]:
    """Return non-authoritative metadata that explains projection quality.

    The enrichment is deliberately separate from the canonical methodology snapshot.
    It reports field origin and compatibility geometry without allowing projected or
    unavailable values to masquerade as native strategy evidence.
    """

    provenance = derive_methodology_provenance(
        stored_methodology=analysis.methodology,
        projected=projected,
    )
    setup = analysis.assessment.setup
    return {
        "methodology_provenance": methodology_provenance_payload(provenance),
        "methodology_completeness": methodology_completeness_payload(provenance),
        "methodology_compatibility_geometry": (
            None if setup is None else project_setup_geometry(setup)
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
