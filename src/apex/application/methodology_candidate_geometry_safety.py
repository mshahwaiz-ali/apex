"""Candidate adapter for shadow geometry-safety auditing."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from apex.application.methodology_candidate_entry_authority import (
    resolve_candidate_entry_authority,
)
from apex.application.methodology_geometry_runtime import GeometryRuntimeContext
from apex.application.methodology_geometry_safety import (
    GeometrySafetyAssessment,
    GeometrySafetyPolicy,
    LaneGeometryPolicy,
    evaluate_geometry_safety,
)
from apex.application.opportunity_portfolio import OpportunityLane
from apex.config.methodology import MethodologySettings
from apex.strategies.contracts import TradeCandidate
from apex.strategies.geometry_audit import derive_execution_stop_geometry


def geometry_safety_policy_from_settings(
    settings: MethodologySettings,
) -> GeometrySafetyPolicy:
    """Convert validated methodology settings into the runtime geometry policy."""

    return GeometrySafetyPolicy(
        lanes={
            lane: LaneGeometryPolicy(
                minimum_tp1_reward_to_risk=config.minimum_tp1_reward_to_risk,
                maximum_stop_distance_pct=config.maximum_stop_distance_pct,
                minimum_target_quality=config.minimum_target_quality,
                minimum_stop_distance_atr=config.minimum_stop_distance_atr,
                minimum_stop_to_cost_ratio=config.minimum_stop_to_cost_ratio,
                maximum_tp1_distance_atr=config.maximum_tp1_distance_atr,
            )
            for lane in OpportunityLane
            for config in (settings.lane_geometry[lane.value],)
        }
    )


DEFAULT_GEOMETRY_SAFETY_POLICY = geometry_safety_policy_from_settings(MethodologySettings())


@dataclass(frozen=True, slots=True)
class CandidateGeometrySafetyAudit:
    """Shadow-only geometry result for one generated candidate."""

    candidate_id: str
    lane: OpportunityLane
    assessment: GeometrySafetyAssessment | None
    missing_measurements: tuple[str, ...]
    reasons: tuple[str, ...]
    measured_lane: OpportunityLane | None = None
    measured_assessment: GeometrySafetyAssessment | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate geometry audit requires candidate identity")
        if not self.reasons:
            raise ValueError("candidate geometry audit requires reasons")
        if len(set(self.missing_measurements)) != len(self.missing_measurements):
            raise ValueError("missing geometry measurements must be unique")
        if self.assessment is not None and self.missing_measurements:
            raise ValueError("complete geometry audit cannot contain missing measurements")
        if self.assessment is None and not self.missing_measurements:
            raise ValueError("unavailable geometry audit requires missing measurements")
        if self.measured_assessment is not None and self.measured_lane is None:
            raise ValueError("measured geometry assessment requires measured lane")


def audit_candidate_geometry_safety(
    candidate: TradeCandidate,
    *,
    candidate_id: str,
    lane: OpportunityLane,
    policy: GeometrySafetyPolicy = DEFAULT_GEOMETRY_SAFETY_POLICY,
    runtime_context: GeometryRuntimeContext | None = None,
) -> CandidateGeometrySafetyAudit:
    """Derive a truthful shadow assessment from explicit candidate measurements."""

    metadata_value = getattr(candidate, "metadata", None)
    if not isinstance(metadata_value, Mapping):
        return CandidateGeometrySafetyAudit(
            candidate_id=candidate_id,
            lane=lane,
            assessment=None,
            missing_measurements=("metadata",),
            reasons=(
                "geometry safety remains shadow-only because candidate metadata is unavailable",
            ),
        )

    metadata = metadata_value
    entry_authority = resolve_candidate_entry_authority(candidate.entry, candidate.metadata)
    selected_entry = entry_authority.selected_entry
    executable_stop = _execution_stop(
        candidate,
        metadata,
        selected_entry=selected_entry,
    )
    if executable_stop is None and runtime_context is not None:
        executable_stop = derive_execution_stop_geometry(
            direction=candidate.direction,
            preferred_entry=selected_entry,
            structural_invalidation=candidate.invalidation.price,
            execution_buffer=runtime_context.execution_buffer,
        ).executable_stop
    expected_cost_pct = _expected_cost_pct(metadata)
    if expected_cost_pct is None and runtime_context is not None:
        expected_cost_pct = runtime_context.expected_cost_pct

    missing: list[str] = []
    if executable_stop is None:
        missing.append("executable_stop")
    if expected_cost_pct is None:
        missing.append("expected_cost_pct")

    if executable_stop is None or expected_cost_pct is None:
        return CandidateGeometrySafetyAudit(
            candidate_id=candidate_id,
            lane=lane,
            assessment=None,
            missing_measurements=tuple(missing),
            reasons=(
                "geometry safety remains shadow-only and unavailable until explicit "
                + ", ".join(missing)
                + " measurements exist",
            ),
        )

    decision_atr = (
        runtime_context.decision_atr
        if runtime_context is not None
        else _optional_number(metadata.get("decision_atr"))
    )
    assessment = evaluate_geometry_safety(
        candidate,
        lane=lane,
        executable_stop=executable_stop,
        target_quality=candidate.quality.target_space_quality * 100.0,
        expected_cost_pct=expected_cost_pct,
        decision_atr=decision_atr,
        selected_entry=selected_entry,
        policy=policy,
    )
    measured_lane = measured_geometry_lane(
        candidate,
        legacy_lane=lane,
        decision_atr=decision_atr,
    )
    measured_assessment = evaluate_geometry_safety(
        candidate,
        lane=measured_lane,
        executable_stop=executable_stop,
        target_quality=candidate.quality.target_space_quality * 100.0,
        expected_cost_pct=expected_cost_pct,
        decision_atr=decision_atr,
        selected_entry=selected_entry,
        policy=policy,
    )
    return CandidateGeometrySafetyAudit(
        candidate_id=candidate_id,
        lane=lane,
        assessment=assessment,
        missing_measurements=(),
        reasons=assessment.reasons,
        measured_lane=measured_lane,
        measured_assessment=measured_assessment,
    )


def measured_geometry_lane(
    candidate: TradeCandidate,
    *,
    legacy_lane: OpportunityLane,
    decision_atr: float | None,
) -> OpportunityLane:
    """Map measured TP1 travel to a policy lane whose horizon can contain it."""

    if decision_atr is None or decision_atr <= 0.0:
        return legacy_lane

    distance = abs(candidate.targets.levels[0].price - candidate.entry.preferred)
    distance_atr = distance / decision_atr

    if distance_atr <= 1.5:
        return legacy_lane if legacy_lane.is_scalp else OpportunityLane.CONFIRMATION_SCALP
    if distance_atr <= 2.0:
        return (
            OpportunityLane.PULLBACK_SCALP
            if legacy_lane is OpportunityLane.PULLBACK_SCALP
            else OpportunityLane.CONFIRMATION_SCALP
        )
    if distance_atr <= 3.0:
        return OpportunityLane.NEARBY_STRUCTURED
    if distance_atr <= 20.0:
        return OpportunityLane.DEVELOPING
    return OpportunityLane.RUNNER


def candidate_geometry_safety_audit_payload(
    audit: CandidateGeometrySafetyAudit,
) -> dict[str, object]:
    """Serialize one shadow geometry audit with actual-versus-required values."""

    legacy_assessment = audit.assessment
    measured_assessment = audit.measured_assessment
    assessment = measured_assessment or legacy_assessment
    effective_lane = audit.measured_lane or audit.lane
    diagnostics = None
    if assessment is not None:
        item = assessment.diagnostics
        diagnostics = {
            "selected_entry": item.selected_entry,
            "entry_zone_low": item.entry_zone_low,
            "entry_zone_high": item.entry_zone_high,
            "executable_stop": item.executable_stop,
            "stop_distance_pct": item.stop_distance_pct,
            "maximum_stop_distance_pct": item.maximum_stop_distance_pct,
            "tp1_price": item.tp1_price,
            "gross_tp1_reward_to_risk": item.gross_tp1_reward_to_risk,
            "net_tp1_reward_to_risk": item.net_tp1_reward_to_risk,
            "gross_reward_distance": item.gross_reward_distance,
            "net_reward_distance": item.net_reward_distance,
            "gross_risk_distance": item.gross_risk_distance,
            "net_risk_distance": item.net_risk_distance,
            "cost_distance": item.cost_distance,
            "stop_to_cost_ratio": item.stop_to_cost_ratio,
            "target_to_cost_ratio": item.target_to_cost_ratio,
            "cost_drag_on_reward_pct": item.cost_drag_on_reward_pct,
            "cost_drag_on_gross_rr_pct": item.cost_drag_on_gross_rr_pct,
            "required_tp1_reward_to_risk": item.required_tp1_reward_to_risk,
            "target_quality": item.target_quality,
            "minimum_target_quality": item.minimum_target_quality,
            "expected_cost_pct": item.expected_cost_pct,
            "stop_distance_atr": item.stop_distance_atr,
            "minimum_stop_distance_atr": item.minimum_stop_distance_atr,
            "minimum_stop_to_cost_ratio": item.minimum_stop_to_cost_ratio,
            "tp1_distance_atr": item.tp1_distance_atr,
            "maximum_tp1_distance_atr": item.maximum_tp1_distance_atr,
            "minimum_viable_tp1_price": item.minimum_viable_tp1_price,
            "minimum_viable_tp1_distance": item.minimum_viable_tp1_distance,
            "minimum_viable_tp1_distance_atr": item.minimum_viable_tp1_distance_atr,
            "available_tp1_price": item.available_tp1_price,
            "available_tp1_distance": item.available_tp1_distance,
            "available_tp1_distance_atr": item.available_tp1_distance_atr,
            "tp1_feasibility_gap": item.tp1_feasibility_gap,
            "tp1_feasibility_gap_atr": item.tp1_feasibility_gap_atr,
            "geometry_feasible_before_quality": item.geometry_feasible_before_quality,
            "feasible_existing_target_count": item.feasible_existing_target_count,
            "nearest_feasible_existing_target_price": (item.nearest_feasible_existing_target_price),
            "nearest_feasible_existing_target_index": (item.nearest_feasible_existing_target_index),
            "no_feasible_target_reason": (
                None
                if item.no_feasible_target_reason is None
                else item.no_feasible_target_reason.value
            ),
        }

    measured = measured_assessment
    legacy_codes = (
        []
        if legacy_assessment is None
        else [item.value for item in legacy_assessment.rejection_codes]
    )
    measured_codes = [] if measured is None else [item.value for item in measured.rejection_codes]
    effective_codes = (
        [] if assessment is None else [item.value for item in assessment.rejection_codes]
    )
    legacy_maximum_tp1_distance_atr = (
        None
        if legacy_assessment is None
        else legacy_assessment.diagnostics.maximum_tp1_distance_atr
    )
    measured_maximum_tp1_distance_atr = (
        None if measured is None else measured.diagnostics.maximum_tp1_distance_atr
    )

    return {
        "candidate_id": audit.candidate_id,
        "lane": effective_lane.value,
        "legacy_lane": audit.lane.value,
        "available": assessment is not None,
        "state": None if assessment is None else assessment.state.value,
        "missing_measurements": list(audit.missing_measurements),
        "rejection_codes": effective_codes,
        "reasons": [] if assessment is None else list(assessment.reasons),
        "diagnostics": diagnostics,
        "legacy_geometry_passed": (None if legacy_assessment is None else legacy_assessment.passed),
        "measured_geometry_lane": (
            None if audit.measured_lane is None else audit.measured_lane.value
        ),
        "measured_geometry_passed": None if measured is None else measured.passed,
        "would_change_geometry_result": (
            None if assessment is None or measured is None else assessment.passed != measured.passed
        ),
        "legacy_geometry_rejection_codes": legacy_codes,
        "measured_geometry_rejection_codes": measured_codes,
        "legacy_maximum_tp1_distance_atr": legacy_maximum_tp1_distance_atr,
        "measured_maximum_tp1_distance_atr": measured_maximum_tp1_distance_atr,
        "measured_geometry_reasons": ([] if measured is None else list(measured.reasons)),
        "measured_lane_basis": "tp1_distance_atr_policy_bucket",
        "effective_geometry_authority": (
            "measured" if measured_assessment is not None else "legacy"
        ),
        "shadow_only": False,
    }


def _execution_stop(
    candidate: TradeCandidate,
    metadata: Mapping[str, object],
    *,
    selected_entry: float,
) -> float | None:
    explicit = _optional_number(metadata.get("executable_stop"))
    if explicit is not None:
        return explicit

    buffer_value = _optional_number(metadata.get("execution_buffer"))
    if buffer_value is None:
        return None
    return derive_execution_stop_geometry(
        direction=candidate.direction,
        preferred_entry=selected_entry,
        structural_invalidation=candidate.invalidation.price,
        execution_buffer=buffer_value,
    ).executable_stop


def _expected_cost_pct(metadata: Mapping[str, object]) -> float | None:
    explicit = _optional_number(metadata.get("expected_cost_pct"))
    if explicit is not None:
        return explicit

    keys = (
        "entry_fee_pct",
        "exit_fee_pct",
        "entry_slippage_pct",
        "exit_slippage_pct",
    )
    components = tuple(_optional_number(metadata.get(key)) for key in keys)
    if any(value is None for value in components):
        return None
    return sum(value for value in components if value is not None)


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("geometry measurement must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError("geometry measurement must be finite and non-negative")
    return number


__all__ = [
    "DEFAULT_GEOMETRY_SAFETY_POLICY",
    "CandidateGeometrySafetyAudit",
    "audit_candidate_geometry_safety",
    "candidate_geometry_safety_audit_payload",
    "geometry_safety_policy_from_settings",
    "measured_geometry_lane",
]
