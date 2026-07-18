"""Interpret stop placement quality without inventing arbitrary thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_contracts import EntryOpportunity, StructuralInvalidation
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class StopQualitySemantics:
    """Truthful structural-stop geometry and quality provenance."""

    canonical_available: bool
    selected_entry_available: bool
    geometry_available: bool
    geometry_authoritative: bool
    entry_reference_price: float | None
    invalidation_price: float | None
    invalidation_distance: float | None
    invalidation_distance_percentage: float | None
    volatility_buffer: float | None
    estimated_slippage: float | None
    structural_distance_before_buffer: float | None
    legacy_quality_score: float | None
    legacy_quality_band: str | None
    legacy_quality_authoritative: bool
    normal_noise_clearance_proven: bool | None
    stop_inside_entry_zone: bool | None
    interpretation: str
    limitations: tuple[str, ...]


def derive_stop_quality_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
    *,
    native_methodology_available: bool,
) -> StopQualitySemantics:
    """Describe stop geometry while leaving unavailable quality evidence unresolved."""

    selected = _selected_opportunity(methodology)
    invalidation = methodology.invalidation
    geometry_available = selected is not None and invalidation is not None

    if geometry_available and selected is not None and invalidation is not None:
        entry_reference = selected.ideal_entry
        distance = abs(entry_reference - invalidation.price)
        distance_percentage = distance / entry_reference * 100.0
        structural_distance = max(
            0.0,
            distance - invalidation.volatility_buffer - invalidation.estimated_slippage,
        )
        inside_zone = selected.zone_low <= invalidation.price <= selected.zone_high
        interpretation = (
            "canonical selected-entry and structural-invalidation geometry are available; "
            "distance, buffer, and execution allowance are reported without applying an "
            "unconfigured universal stop-quality threshold"
        )
    else:
        entry_reference = None
        distance = None
        distance_percentage = None
        structural_distance = None
        inside_zone = None
        interpretation = (
            "canonical stop-quality geometry is incomplete because an authoritative selected "
            "entry and structural invalidation are not both available"
        )

    legacy_score = None if setup is None else setup.stop_loss.quality_score
    legacy_band = None if setup is None else setup.stop_loss.quality_band.value

    return StopQualitySemantics(
        canonical_available=invalidation is not None,
        selected_entry_available=methodology.selected_entry is not None,
        geometry_available=geometry_available,
        geometry_authoritative=bool(native_methodology_available and geometry_available),
        entry_reference_price=entry_reference,
        invalidation_price=None if invalidation is None else invalidation.price,
        invalidation_distance=distance,
        invalidation_distance_percentage=distance_percentage,
        volatility_buffer=(
            None if invalidation is None else invalidation.volatility_buffer
        ),
        estimated_slippage=(
            None if invalidation is None else invalidation.estimated_slippage
        ),
        structural_distance_before_buffer=structural_distance,
        legacy_quality_score=legacy_score,
        legacy_quality_band=legacy_band,
        legacy_quality_authoritative=False,
        normal_noise_clearance_proven=None,
        stop_inside_entry_zone=inside_zone,
        interpretation=interpretation,
        limitations=(
            "ATR, realized-volatility, and normal-noise clearance evidence are not present in the canonical invalidation contract",
            "absolute distance alone cannot establish that a stop is structurally strong or outside normal noise",
            "legacy stop-quality scores remain compatibility metadata and are not canonical methodology authority",
            "position size, leverage, and acceptable monetary loss must not alter the structural invalidation level",
            "directional wrong-side validation requires direction to be explicit in the canonical methodology state",
        ),
    )


def stop_quality_semantics_payload(
    semantics: StopQualitySemantics,
) -> dict[str, Any]:
    """Serialize structural-stop quality interpretation."""

    return {
        "canonical_available": semantics.canonical_available,
        "selected_entry_available": semantics.selected_entry_available,
        "geometry_available": semantics.geometry_available,
        "geometry_authoritative": semantics.geometry_authoritative,
        "entry_reference_price": semantics.entry_reference_price,
        "invalidation_price": semantics.invalidation_price,
        "invalidation_distance": semantics.invalidation_distance,
        "invalidation_distance_percentage": semantics.invalidation_distance_percentage,
        "volatility_buffer": semantics.volatility_buffer,
        "estimated_slippage": semantics.estimated_slippage,
        "structural_distance_before_buffer": semantics.structural_distance_before_buffer,
        "legacy_quality_score": semantics.legacy_quality_score,
        "legacy_quality_band": semantics.legacy_quality_band,
        "legacy_quality_authoritative": semantics.legacy_quality_authoritative,
        "normal_noise_clearance_proven": semantics.normal_noise_clearance_proven,
        "stop_inside_entry_zone": semantics.stop_inside_entry_zone,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _selected_opportunity(
    methodology: MethodologySnapshot,
) -> EntryOpportunity | None:
    decision = methodology.selected_entry
    return None if decision is None else decision.opportunity


__all__ = [
    "StopQualitySemantics",
    "derive_stop_quality_semantics",
    "stop_quality_semantics_payload",
]
