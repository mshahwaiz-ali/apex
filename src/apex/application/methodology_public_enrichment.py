"""Build truthful methodology metadata for public discovery output."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_actionability_semantics import (
    actionability_semantics_payload,
    derive_actionability_semantics,
)
from apex.application.methodology_auxiliary_evidence import MethodologyAuxiliaryEvidence
from apex.application.methodology_confidence_semantics import (
    confidence_semantics_payload,
    derive_confidence_semantics,
)
from apex.application.methodology_confirmation_source_semantics import (
    confirmation_source_semantics_payload,
    derive_confirmation_source_semantics,
)
from apex.application.methodology_contradiction_semantics import (
    contradiction_semantics_payload,
    derive_contradiction_semantics,
)
from apex.application.methodology_entry_opportunity_semantics import (
    derive_entry_opportunity_semantics,
    entry_opportunity_semantics_payload,
)
from apex.application.methodology_evidence_freshness_semantics import (
    derive_evidence_freshness_semantics,
    evidence_freshness_semantics_payload,
)
from apex.application.methodology_evidence_independence_semantics import (
    derive_evidence_independence_semantics,
    evidence_independence_semantics_payload,
)
from apex.application.methodology_execution_geometry_semantics import (
    derive_execution_geometry_semantics,
    execution_geometry_semantics_payload,
)
from apex.application.methodology_expiry_semantics import (
    derive_expiry_semantics,
    expiry_semantics_payload,
)
from apex.application.methodology_geometry_projection import project_setup_geometry
from apex.application.methodology_invalidation_semantics import (
    derive_invalidation_semantics,
    invalidation_semantics_payload,
)
from apex.application.methodology_management_semantics import (
    derive_management_semantics,
    management_semantics_payload,
)
from apex.application.methodology_market_state_semantics import (
    derive_market_state_semantics,
    market_state_semantics_payload,
)
from apex.application.methodology_market_usability_semantics import (
    derive_market_usability_semantics,
    market_usability_semantics_payload,
)
from apex.application.methodology_provenance import (
    derive_methodology_provenance,
    methodology_completeness_payload,
    methodology_provenance_payload,
)
from apex.application.methodology_ranking_integrity_semantics import (
    derive_ranking_integrity_semantics,
    ranking_integrity_semantics_payload,
)
from apex.application.methodology_rejection_semantics import (
    derive_rejection_semantics,
    rejection_semantics_payload,
)
from apex.application.methodology_score_semantics import (
    derive_score_semantics,
    score_semantics_payload,
)
from apex.application.methodology_selected_entry_semantics import (
    derive_selected_entry_semantics,
    selected_entry_semantics_payload,
)
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_source_bundle import MethodologySourceBundle
from apex.application.methodology_stop_noise_contracts import StopNoiseEvidence
from apex.application.methodology_stop_quality_semantics import (
    derive_stop_quality_semantics,
    stop_quality_semantics_payload,
)
from apex.application.methodology_strategy_fit_semantics import (
    derive_strategy_fit_semantics,
    strategy_fit_semantics_payload,
)
from apex.application.methodology_target_feasibility_semantics import (
    derive_target_feasibility_semantics,
    target_feasibility_semantics_payload,
)
from apex.application.methodology_target_horizon_semantics import (
    derive_target_horizon_semantics,
    target_horizon_semantics_payload,
)
from apex.application.methodology_timeframe_coverage_semantics import (
    derive_timeframe_coverage_semantics,
    timeframe_coverage_semantics_payload,
)


def methodology_public_enrichment(
    analysis: SymbolAnalysis,
    projected: MethodologySnapshot,
    source_bundle: MethodologySourceBundle | None = None,
    stop_noise_evidence: StopNoiseEvidence | None = None,
    auxiliary_evidence: MethodologyAuxiliaryEvidence | None = None,
) -> dict[str, Any]:
    """Return transparent evidence, entry, ranking, and execution semantics.

    The enrichment remains separate from the canonical methodology snapshot. It
    reports field origin and compatibility geometry without allowing projected or
    unavailable values to masquerade as native evidence, independent confirmation,
    calibrated probability, closed-candle confirmation, verified strategy
    eligibility, complete timeframe coverage, usable execution conditions,
    proven elapsed-bar expiry, authoritative selected-entry decisions,
    rank-authorized execution, canonical geometry, authoritative actionability,
    hidden rejection, executed lifecycle actions, or a universal target horizon.
    """

    effective_auxiliary = (
        analysis.methodology_auxiliary_evidence
        if auxiliary_evidence is None
        else auxiliary_evidence
    )
    effective_source_bundle, effective_stop_noise = _resolve_auxiliary_evidence(
        projected,
        source_bundle=source_bundle,
        stop_noise_evidence=stop_noise_evidence,
        auxiliary_evidence=effective_auxiliary,
    )
    source_candles = (
        () if effective_source_bundle is None else effective_source_bundle.source_candles
    )
    source_references = (
        () if effective_source_bundle is None else effective_source_bundle.evidence_references
    )
    confirmation_candle = (
        None if effective_source_bundle is None else effective_source_bundle.confirmation_source
    )

    provenance = derive_methodology_provenance(
        stored_methodology=analysis.methodology,
        projected=projected,
    )
    setup = analysis.assessment.setup
    native_available = analysis.methodology is not None
    actionability = derive_actionability_semantics(setup, projected)
    confidence = derive_confidence_semantics(
        projected.confidence,
        projected.calibration,
    )
    confirmation_source = derive_confirmation_source_semantics(
        projected,
        confirmation_candle,
    )
    contradictions = derive_contradiction_semantics(projected)
    entry_opportunities = derive_entry_opportunity_semantics(projected)
    evidence_freshness = derive_evidence_freshness_semantics(
        projected,
        source_candles,
        source_references,
    )
    evidence_independence = derive_evidence_independence_semantics(projected)
    execution_geometry = derive_execution_geometry_semantics(
        setup,
        projected,
        native_methodology_available=native_available,
    )
    expiry = derive_expiry_semantics(projected)
    invalidation = derive_invalidation_semantics(
        setup,
        projected,
        native_methodology_available=native_available,
    )
    management = derive_management_semantics(projected)
    market_state = derive_market_state_semantics(projected)
    market_usability = derive_market_usability_semantics(projected)
    ranking_integrity = derive_ranking_integrity_semantics(analysis, projected)
    rejections = derive_rejection_semantics(projected)
    score = derive_score_semantics(setup, projected)
    selected_entry = derive_selected_entry_semantics(projected)
    stop_quality = derive_stop_quality_semantics(
        setup,
        projected,
        native_methodology_available=native_available,
        noise_evidence=effective_stop_noise,
    )
    strategy_fit = derive_strategy_fit_semantics(setup, projected)
    target_feasibility = derive_target_feasibility_semantics(
        projected,
        native_methodology_available=native_available,
        execution_costs=projected.execution_costs,
        obstacle_evidence=projected.target_obstacles,
    )
    target_horizon = derive_target_horizon_semantics(projected)
    timeframe_coverage = derive_timeframe_coverage_semantics(analysis)
    return {
        "methodology_provenance": methodology_provenance_payload(provenance),
        "methodology_completeness": methodology_completeness_payload(provenance),
        "methodology_compatibility_geometry": (
            None if setup is None else project_setup_geometry(setup)
        ),
        "methodology_actionability_semantics": actionability_semantics_payload(actionability),
        "methodology_confidence_semantics": confidence_semantics_payload(confidence),
        "methodology_confirmation_source_semantics": (
            confirmation_source_semantics_payload(confirmation_source)
        ),
        "methodology_contradiction_semantics": contradiction_semantics_payload(contradictions),
        "methodology_entry_opportunity_semantics": entry_opportunity_semantics_payload(
            entry_opportunities
        ),
        "methodology_evidence_freshness_semantics": evidence_freshness_semantics_payload(
            evidence_freshness
        ),
        "methodology_evidence_independence_semantics": (
            evidence_independence_semantics_payload(evidence_independence)
        ),
        "methodology_execution_geometry_semantics": execution_geometry_semantics_payload(
            execution_geometry
        ),
        "methodology_expiry_semantics": expiry_semantics_payload(expiry),
        "methodology_invalidation_semantics": invalidation_semantics_payload(invalidation),
        "methodology_management_semantics": management_semantics_payload(management),
        "methodology_market_state_semantics": market_state_semantics_payload(market_state),
        "methodology_market_usability_semantics": market_usability_semantics_payload(
            market_usability
        ),
        "methodology_ranking_integrity_semantics": ranking_integrity_semantics_payload(
            ranking_integrity
        ),
        "methodology_rejection_semantics": rejection_semantics_payload(rejections),
        "methodology_score_semantics": score_semantics_payload(score),
        "methodology_selected_entry_semantics": selected_entry_semantics_payload(selected_entry),
        "methodology_stop_quality_semantics": stop_quality_semantics_payload(stop_quality),
        "methodology_strategy_fit_semantics": strategy_fit_semantics_payload(strategy_fit),
        "methodology_target_feasibility_semantics": target_feasibility_semantics_payload(
            target_feasibility
        ),
        "methodology_target_horizon_semantics": target_horizon_semantics_payload(target_horizon),
        "methodology_timeframe_coverage_semantics": timeframe_coverage_semantics_payload(
            timeframe_coverage
        ),
        "methodology_candlestick_evidence": _candlestick_evidence(analysis),
        "methodology_projection_authoritative": native_available,
        "methodology_projection_notice": _projection_notice(analysis),
    }


def _resolve_auxiliary_evidence(
    projected: MethodologySnapshot,
    *,
    source_bundle: MethodologySourceBundle | None,
    stop_noise_evidence: StopNoiseEvidence | None,
    auxiliary_evidence: MethodologyAuxiliaryEvidence | None,
) -> tuple[MethodologySourceBundle | None, StopNoiseEvidence | None]:
    if auxiliary_evidence is None:
        if source_bundle is not None:
            source_bundle.validate_for(projected)
        return source_bundle, stop_noise_evidence

    auxiliary_evidence.validate_for(projected)
    if (
        source_bundle is not None
        and auxiliary_evidence.source_bundle is not None
        and source_bundle != auxiliary_evidence.source_bundle
    ):
        raise ValueError("conflicting methodology source bundles were provided")
    if (
        stop_noise_evidence is not None
        and auxiliary_evidence.stop_noise is not None
        and stop_noise_evidence != auxiliary_evidence.stop_noise
    ):
        raise ValueError("conflicting methodology stop-noise evidence was provided")

    effective_source = source_bundle or auxiliary_evidence.source_bundle
    effective_noise = stop_noise_evidence or auxiliary_evidence.stop_noise
    if effective_source is not None:
        effective_source.validate_for(projected)
    return effective_source, effective_noise


def _projection_notice(analysis: SymbolAnalysis) -> str:
    if analysis.methodology is not None:
        return "native methodology values remain authoritative"
    if analysis.assessment.setup is None:
        return "no selected setup exists; unavailable methodology fields remain deferred"
    return (
        "compatibility values were projected from the selected legacy setup; "
        "unavailable fields were not fabricated"
    )


def _candlestick_evidence(analysis: SymbolAnalysis) -> list[object]:
    diagnostics = analysis.phase5_diagnostics or {}
    value = diagnostics.get("candlestick_evidence")
    if not isinstance(value, list):
        return []
    deduplicated: list[object] = []
    seen: set[tuple[object, ...]] = set()
    for item in value:
        if not isinstance(item, dict):
            deduplicated.append(item)
            continue
        key = (
            item.get("timeframe"),
            item.get("pattern_id"),
            item.get("direction"),
            item.get("completion_state"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


__all__ = ["methodology_public_enrichment"]
