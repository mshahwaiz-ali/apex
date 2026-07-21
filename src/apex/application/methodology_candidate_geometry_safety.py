"""Candidate adapter for shadow geometry-safety auditing."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

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
    executable_stop = _execution_stop(candidate, metadata)
    if executable_stop is None and runtime_context is not None:
        executable_stop = derive_execution_stop_geometry(
            direction=candidate.direction,
            preferred_entry=candidate.entry.preferred,
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

    assessment = evaluate_geometry_safety(
        candidate,
        lane=lane,
        executable_stop=executable_stop,
        target_quality=candidate.quality.target_space_quality * 100.0,
        expected_cost_pct=expected_cost_pct,
        policy=policy,
    )
    return CandidateGeometrySafetyAudit(
        candidate_id=candidate_id,
        lane=lane,
        assessment=assessment,
        missing_measurements=(),
        reasons=assessment.reasons,
    )


def candidate_geometry_safety_audit_payload(
    audit: CandidateGeometrySafetyAudit,
) -> dict[str, object]:
    """Serialize one shadow geometry audit with actual-versus-required values."""

    assessment = audit.assessment
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
            "required_tp1_reward_to_risk": item.required_tp1_reward_to_risk,
            "target_quality": item.target_quality,
            "minimum_target_quality": item.minimum_target_quality,
            "expected_cost_pct": item.expected_cost_pct,
        }

    return {
        "candidate_id": audit.candidate_id,
        "lane": audit.lane.value,
        "available": assessment is not None,
        "state": None if assessment is None else assessment.state.value,
        "missing_measurements": list(audit.missing_measurements),
        "rejection_codes": (
            [] if assessment is None else [item.value for item in assessment.rejection_codes]
        ),
        "reasons": list(audit.reasons),
        "diagnostics": diagnostics,
        "shadow_only": True,
    }


def _execution_stop(
    candidate: TradeCandidate,
    metadata: Mapping[str, object],
) -> float | None:
    explicit = _optional_number(metadata.get("executable_stop"))
    if explicit is not None:
        return explicit

    buffer_value = _optional_number(metadata.get("execution_buffer"))
    if buffer_value is None:
        return None
    return derive_execution_stop_geometry(
        direction=candidate.direction,
        preferred_entry=candidate.entry.preferred,
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
]
