"""Interpret stop placement quality without inventing arbitrary thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_contracts import EntryOpportunity
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_stop_noise_contracts import StopNoiseEvidence
from apex.strategies.contracts import TradeDirection


@dataclass(frozen=True, slots=True)
class StopQualitySemantics:
    """Truthful structural-stop geometry and quality provenance."""

    canonical_available: bool
    selected_entry_available: bool
    direction_available: bool
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
    noise_evidence_available: bool
    noise_measure: str | None
    noise_value: float | None
    noise_timeframe: str | None
    noise_sample_size: int | None
    noise_source: str | None
    required_clearance_multiplier: float | None
    required_clearance_distance: float | None
    stop_distance_in_noise_units: float | None
    normal_noise_clearance_proven: bool | None
    stop_inside_entry_zone: bool | None
    directionally_validated: bool
    stop_on_correct_side: bool | None
    interpretation: str
    limitations: tuple[str, ...]


def derive_stop_quality_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
    *,
    native_methodology_available: bool,
    noise_evidence: StopNoiseEvidence | None = None,
) -> StopQualitySemantics:
    """Describe stop geometry and only claim noise clearance from explicit evidence."""

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
        correct_side = _stop_on_correct_side(methodology, selected)
    else:
        entry_reference = None
        distance = None
        distance_percentage = None
        structural_distance = None
        inside_zone = None
        correct_side = None

    distance_in_noise = (
        None
        if distance is None or noise_evidence is None
        else distance / noise_evidence.value
    )
    noise_clearance = (
        None
        if distance is None or noise_evidence is None
        else distance >= noise_evidence.required_clearance_distance
    )

    if not geometry_available:
        interpretation = (
            "canonical stop-quality geometry is incomplete because an authoritative selected "
            "entry and structural invalidation are not both available"
        )
    elif noise_evidence is None:
        interpretation = (
            "canonical stop geometry is available, but normal-noise clearance remains unknown "
            "because no ATR or realized-noise evidence is attached"
        )
    elif noise_clearance:
        interpretation = (
            "the structural stop clears the explicitly configured normal-noise distance for the "
            "recorded measure and timeframe; this is not a universal stop-width rule"
        )
    else:
        interpretation = (
            "the structural stop does not clear the explicitly configured normal-noise distance; "
            "the setup may require rejection or re-construction rather than arbitrary widening"
        )

    legacy_score = None if setup is None else setup.stop_loss.quality_score
    legacy_band = None if setup is None else setup.stop_loss.quality_band.value
    directionally_validated = methodology.direction is not None and correct_side is not None
    limitations = [
        "absolute distance alone cannot establish that a stop is structurally strong or outside normal noise",
        "legacy stop-quality scores remain compatibility metadata and are not canonical methodology authority",
        "position size, leverage, and acceptable monetary loss must not alter the structural invalidation level",
    ]
    if noise_evidence is None:
        limitations.insert(
            0,
            "ATR, realized-range, or realized-volatility evidence is unavailable, so normal-noise clearance is not claimed",
        )
    else:
        limitations.append(
            "the configured clearance multiplier is strategy-specific evidence, not a universal market threshold"
        )

    return StopQualitySemantics(
        canonical_available=invalidation is not None,
        selected_entry_available=methodology.selected_entry is not None,
        direction_available=methodology.direction is not None,
        geometry_available=geometry_available,
        geometry_authoritative=bool(
            native_methodology_available and geometry_available and directionally_validated
        ),
        entry_reference_price=entry_reference,
        invalidation_price=None if invalidation is None else invalidation.price,
        invalidation_distance=distance,
        invalidation_distance_percentage=distance_percentage,
        volatility_buffer=None if invalidation is None else invalidation.volatility_buffer,
        estimated_slippage=None if invalidation is None else invalidation.estimated_slippage,
        structural_distance_before_buffer=structural_distance,
        legacy_quality_score=legacy_score,
        legacy_quality_band=legacy_band,
        legacy_quality_authoritative=False,
        noise_evidence_available=noise_evidence is not None,
        noise_measure=None if noise_evidence is None else noise_evidence.measure.value,
        noise_value=None if noise_evidence is None else noise_evidence.value,
        noise_timeframe=None if noise_evidence is None else noise_evidence.timeframe,
        noise_sample_size=None if noise_evidence is None else noise_evidence.sample_size,
        noise_source=None if noise_evidence is None else noise_evidence.source,
        required_clearance_multiplier=(
            None if noise_evidence is None else noise_evidence.required_clearance_multiplier
        ),
        required_clearance_distance=(
            None if noise_evidence is None else noise_evidence.required_clearance_distance
        ),
        stop_distance_in_noise_units=distance_in_noise,
        normal_noise_clearance_proven=noise_clearance,
        stop_inside_entry_zone=inside_zone,
        directionally_validated=directionally_validated,
        stop_on_correct_side=correct_side,
        interpretation=interpretation,
        limitations=tuple(limitations),
    )


def stop_quality_semantics_payload(
    semantics: StopQualitySemantics,
) -> dict[str, Any]:
    """Serialize structural-stop quality interpretation."""

    return {
        "canonical_available": semantics.canonical_available,
        "selected_entry_available": semantics.selected_entry_available,
        "direction_available": semantics.direction_available,
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
        "noise_evidence_available": semantics.noise_evidence_available,
        "noise_measure": semantics.noise_measure,
        "noise_value": semantics.noise_value,
        "noise_timeframe": semantics.noise_timeframe,
        "noise_sample_size": semantics.noise_sample_size,
        "noise_source": semantics.noise_source,
        "required_clearance_multiplier": semantics.required_clearance_multiplier,
        "required_clearance_distance": semantics.required_clearance_distance,
        "stop_distance_in_noise_units": semantics.stop_distance_in_noise_units,
        "normal_noise_clearance_proven": semantics.normal_noise_clearance_proven,
        "stop_inside_entry_zone": semantics.stop_inside_entry_zone,
        "directionally_validated": semantics.directionally_validated,
        "stop_on_correct_side": semantics.stop_on_correct_side,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _selected_opportunity(
    methodology: MethodologySnapshot,
) -> EntryOpportunity | None:
    decision = methodology.selected_entry
    return None if decision is None else decision.opportunity


def _stop_on_correct_side(
    methodology: MethodologySnapshot,
    entry: EntryOpportunity,
) -> bool | None:
    if methodology.direction is None or methodology.invalidation is None:
        return None
    if methodology.direction is TradeDirection.LONG:
        return methodology.invalidation.price < entry.zone_low
    return methodology.invalidation.price > entry.zone_high


__all__ = [
    "StopQualitySemantics",
    "derive_stop_quality_semantics",
    "stop_quality_semantics_payload",
]
