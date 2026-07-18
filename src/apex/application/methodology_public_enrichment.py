"""Build truthful methodology metadata for public discovery output."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_actionability_semantics import (
    actionability_semantics_payload,
    derive_actionability_semantics,
)
from apex.application.methodology_confidence_semantics import (
    confidence_semantics_payload,
    derive_confidence_semantics,
)
from apex.application.methodology_confirmation_source_semantics import (
    confirmation_source_semantics_payload,
    derive_confirmation_source_semantics,
)
from apex.application.methodology_entry_opportunity_semantics import (
    derive_entry_opportunity_semantics,
    entry_opportunity_semantics_payload,
)
from apex.application.methodology_evidence_freshness_semantics import (
    derive_evidence_freshness_semantics,
    evidence_freshness_semantics_payload,
)
from apex.application.methodology_execution_geometry_semantics import (
    derive_execution_geometry_semantics,
    execution_geometry_semantics_payload,
)
from apex.application.methodology_geometry_projection import project_setup_geometry
from apex.application.methodology_invalidation_semantics import (
    derive_invalidation_semantics,
    invalidation_semantics_payload,
)
from apex.application.methodology_market_state_semantics import (
    derive_market_state_semantics,
    market_state_semantics_payload,
)
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
from apex.application.methodology_strategy_fit_semantics import (
    derive_strategy_fit_semantics,
    strategy_fit_semantics_payload,
)
from apex.application.methodology_target_horizon_semantics import (
    derive_target_horizon_semantics,
    target_horizon_semantics_payload,
)


def methodology_public_enrichment(
    analysis: SymbolAnalysis,
    projected: MethodologySnapshot,
) -> dict[str, Any]:
    """Return transparent projection, state, evidence, and execution semantics.

    The enrichment remains separate from the canonical methodology snapshot. It
    reports field origin and compatibility geometry without allowing projected or
    unavailable values to masquerade as native evidence, calibrated probability,
    closed-candle confirmation, verified strategy eligibility, canonical execution
    geometry, authoritative actionability, hidden rejection, score-authorized
    execution, or a universal target horizon.
    """

    provenance = derive_methodology_provenance(
        stored_methodology=analysis.methodology,
        projected=projected,
    )
    setup = analysis.assessment.setup
    native_available = analysis.methodology is not None
    actionability = derive_actionability_semantics(setup, projected)
    confidence = derive_confidence_semantics(projected.confidence)
    confirmation_source = derive_confirmation_source_semantics(projected)
    entry_opportunities = derive_entry_opportunity_semantics(projected)
    evidence_freshness = derive_evidence_freshness_semantics(projected)
    execution_geometry = derive_execution_geometry_semantics(
        setup,
        projected,
        native_methodology_available=native_available,
    )
    invalidation = derive_invalidation_semantics(
        setup,
        projected,
        native_methodology_available=native_available,
    )
    market_state = derive_market_state_semantics(projected)
    rejections = derive_rejection_semantics(projected)
    score = derive_score_semantics(setup, projected)
    strategy_fit = derive_strategy_fit_semantics(setup, projected)
    target_horizon = derive_target_horizon_semantics(projected)
    return {
        "methodology_provenance": methodology_provenance_payload(provenance),
        "methodology_completeness": methodology_completeness_payload(provenance),
        "methodology_compatibility_geometry": (
            None if setup is None else project_setup_geometry(setup)
        ),
        "methodology_actionability_semantics": actionability_semantics_payload(
            actionability
        ),
        "methodology_confidence_semantics": confidence_semantics_payload(confidence),
        "methodology_confirmation_source_semantics": (
            confirmation_source_semantics_payload(confirmation_source)
        ),
        "methodology_entry_opportunity_semantics": entry_opportunity_semantics_payload(
            entry_opportunities
        ),
        "methodology_evidence_freshness_semantics": evidence_freshness_semantics_payload(
            evidence_freshness
        ),
        "methodology_execution_geometry_semantics": execution_geometry_semantics_payload(
            execution_geometry
        ),
        "methodology_invalidation_semantics": invalidation_semantics_payload(invalidation),
        "methodology_market_state_semantics": market_state_semantics_payload(market_state),
        "methodology_rejection_semantics": rejection_semantics_payload(rejections),
        "methodology_score_semantics": score_semantics_payload(score),
        "methodology_strategy_fit_semantics": strategy_fit_semantics_payload(strategy_fit),
        "methodology_target_horizon_semantics": target_horizon_semantics_payload(
            target_horizon
        ),
        "methodology_projection_authoritative": native_available,
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
