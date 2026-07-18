"""Interpret target feasibility without imposing a universal reward threshold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import TargetCandidate
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_target_context_contracts import (
    ExecutionCostEstimate,
    TargetObstacleEvidence,
    TargetObstacleRelation,
)
from apex.strategies.contracts import TradeDirection


@dataclass(frozen=True, slots=True)
class TargetFeasibilityItem:
    """Derived geometry for one canonical target candidate."""

    role: str
    price: float
    source: str
    conditional: bool
    declared_move_percentage: float
    derived_move_percentage: float | None
    net_move_percentage: float | None
    declared_risk_multiple: float
    derived_gross_risk_multiple: float | None
    derived_net_risk_multiple: float | None
    declared_geometry_consistent: bool | None
    on_correct_side: bool | None
    obstacle_price: float | None
    obstacle_relation: str | None
    obstacle_structure_kind: str | None
    obstacle_source: str | None
    clearance_buffer_percentage: float | None
    room_to_obstacle_percentage: float | None
    clear_room_proven: bool | None


@dataclass(frozen=True, slots=True)
class TargetFeasibilitySemantics:
    """Truthful target geometry, provenance, costs, and obstacle evidence."""

    direction_available: bool
    selected_entry_available: bool
    invalidation_available: bool
    gross_geometry_available: bool
    geometry_authoritative: bool
    entry_reference_price: float | None
    risk_distance: float | None
    target_count: int
    targets: tuple[TargetFeasibilityItem, ...]
    costs_available: bool
    total_cost_percentage: float | None
    cost_source: str | None
    net_reward_geometry_available: bool
    obstacle_evidence_count: int
    obstacle_room_proven: bool | None
    directionally_validated: bool
    all_targets_on_correct_side: bool | None
    universal_minimum_risk_reward_applied: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_target_feasibility_semantics(
    methodology: MethodologySnapshot,
    *,
    native_methodology_available: bool,
    execution_costs: ExecutionCostEstimate | None = None,
    obstacle_evidence: tuple[TargetObstacleEvidence, ...] = (),
) -> TargetFeasibilitySemantics:
    """Derive gross and evidenced net geometry without fabricated assumptions."""

    _validate_obstacle_evidence(methodology, obstacle_evidence)
    obstacle_by_role = {item.target_role: item for item in obstacle_evidence}
    decision = methodology.selected_entry
    invalidation = methodology.invalidation
    opportunity = None if decision is None else decision.opportunity
    entry = None if opportunity is None else opportunity.ideal_entry
    risk_distance = (
        None if entry is None or invalidation is None else abs(entry - invalidation.price)
    )
    gross_available = risk_distance is not None and risk_distance > 0.0
    items = tuple(
        _target_item(
            target,
            methodology=methodology,
            entry=entry,
            risk_distance=risk_distance,
            execution_costs=execution_costs,
            obstacle=obstacle_by_role.get(target.role),
        )
        for target in methodology.targets
    )
    directional_results = tuple(
        item.on_correct_side for item in items if item.on_correct_side is not None
    )
    directionally_validated = bool(items) and len(directional_results) == len(items)
    all_correct = all(directional_results) if directionally_validated else None
    room_results = tuple(
        item.clear_room_proven for item in items if item.clear_room_proven is not None
    )
    obstacle_room_proven = all(room_results) if items and len(room_results) == len(items) else None
    net_available = bool(execution_costs is not None and gross_available)

    if not methodology.targets:
        interpretation = "no canonical target candidates are available"
    elif not gross_available:
        interpretation = (
            "canonical targets exist, but reward geometry requires an authoritative selected "
            "entry and structural invalidation"
        )
    elif execution_costs is None and not obstacle_evidence:
        interpretation = (
            "gross target geometry is available; execution costs and opposing-structure room "
            "remain unavailable rather than assumed"
        )
    elif not directionally_validated:
        interpretation = (
            "reward geometry is available, but canonical direction is unavailable so target-side "
            "correctness cannot be proven"
        )
    else:
        interpretation = (
            "target geometry uses canonical entry and invalidation, with net reward and obstacle "
            "room reported only where explicit evidence exists; no universal minimum R:R applies"
        )

    limitations = [
        "strategy-specific expectancy is required before judging whether any R "
        "multiple is sufficient",
        "declared and derived R multiples may differ because upstream calculations "
        "may use different entry or cost assumptions",
    ]
    if execution_costs is None:
        limitations.insert(
            0,
            "fees, funding, spread, and target-exit slippage are unavailable, so net "
            "reward geometry is not claimed",
        )
    if obstacle_room_proven is None:
        limitations.insert(
            0,
            "target source text alone does not prove clear room before opposing structure",
        )

    return TargetFeasibilitySemantics(
        direction_available=methodology.direction is not None,
        selected_entry_available=decision is not None,
        invalidation_available=invalidation is not None,
        gross_geometry_available=gross_available,
        geometry_authoritative=bool(
            native_methodology_available and gross_available and directionally_validated
        ),
        entry_reference_price=entry,
        risk_distance=risk_distance,
        target_count=len(methodology.targets),
        targets=items,
        costs_available=execution_costs is not None,
        total_cost_percentage=(
            None if execution_costs is None else execution_costs.total_percentage
        ),
        cost_source=None if execution_costs is None else execution_costs.source,
        net_reward_geometry_available=net_available,
        obstacle_evidence_count=len(obstacle_evidence),
        obstacle_room_proven=obstacle_room_proven,
        directionally_validated=directionally_validated,
        all_targets_on_correct_side=all_correct,
        universal_minimum_risk_reward_applied=False,
        interpretation=interpretation,
        limitations=tuple(limitations),
    )


def target_feasibility_semantics_payload(
    semantics: TargetFeasibilitySemantics,
) -> dict[str, Any]:
    """Serialize target feasibility interpretation."""

    return {
        "direction_available": semantics.direction_available,
        "selected_entry_available": semantics.selected_entry_available,
        "invalidation_available": semantics.invalidation_available,
        "gross_geometry_available": semantics.gross_geometry_available,
        "geometry_authoritative": semantics.geometry_authoritative,
        "entry_reference_price": semantics.entry_reference_price,
        "risk_distance": semantics.risk_distance,
        "target_count": semantics.target_count,
        "targets": [
            {
                "role": item.role,
                "price": item.price,
                "source": item.source,
                "conditional": item.conditional,
                "declared_move_percentage": item.declared_move_percentage,
                "derived_move_percentage": item.derived_move_percentage,
                "net_move_percentage": item.net_move_percentage,
                "declared_risk_multiple": item.declared_risk_multiple,
                "derived_gross_risk_multiple": item.derived_gross_risk_multiple,
                "derived_net_risk_multiple": item.derived_net_risk_multiple,
                "declared_geometry_consistent": item.declared_geometry_consistent,
                "on_correct_side": item.on_correct_side,
                "obstacle_price": item.obstacle_price,
                "obstacle_relation": item.obstacle_relation,
                "obstacle_structure_kind": item.obstacle_structure_kind,
                "obstacle_source": item.obstacle_source,
                "clearance_buffer_percentage": item.clearance_buffer_percentage,
                "room_to_obstacle_percentage": item.room_to_obstacle_percentage,
                "clear_room_proven": item.clear_room_proven,
            }
            for item in semantics.targets
        ],
        "costs_available": semantics.costs_available,
        "total_cost_percentage": semantics.total_cost_percentage,
        "cost_source": semantics.cost_source,
        "net_reward_geometry_available": semantics.net_reward_geometry_available,
        "obstacle_evidence_count": semantics.obstacle_evidence_count,
        "obstacle_room_proven": semantics.obstacle_room_proven,
        "directionally_validated": semantics.directionally_validated,
        "all_targets_on_correct_side": semantics.all_targets_on_correct_side,
        "universal_minimum_risk_reward_applied": (semantics.universal_minimum_risk_reward_applied),
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _target_item(
    target: TargetCandidate,
    *,
    methodology: MethodologySnapshot,
    entry: float | None,
    risk_distance: float | None,
    execution_costs: ExecutionCostEstimate | None,
    obstacle: TargetObstacleEvidence | None,
) -> TargetFeasibilityItem:
    gross_distance = None if entry is None else abs(target.price - entry)
    derived_move = (
        None if gross_distance is None or entry is None else gross_distance / entry * 100.0
    )
    derived_r = (
        None
        if gross_distance is None or risk_distance is None or risk_distance <= 0.0
        else gross_distance / risk_distance
    )
    cost_distance = (
        None
        if entry is None or execution_costs is None
        else entry * execution_costs.total_percentage / 100.0
    )
    net_distance = (
        None
        if gross_distance is None or cost_distance is None
        else max(0.0, gross_distance - cost_distance)
    )
    net_move = None if net_distance is None or entry is None else net_distance / entry * 100.0
    net_r = (
        None
        if net_distance is None or risk_distance is None or risk_distance <= 0.0
        else net_distance / risk_distance
    )
    consistent = (
        None
        if derived_r is None
        else abs(derived_r - target.risk_multiple) <= max(0.05, derived_r * 0.05)
    )
    room_percentage = (
        None
        if entry is None or obstacle is None
        else abs(obstacle.obstacle_price - target.price) / entry * 100.0
    )
    clear_room = (
        None
        if obstacle is None
        else obstacle.relation is TargetObstacleRelation.BEFORE
        and room_percentage is not None
        and room_percentage >= obstacle.clearance_buffer_percentage
    )
    return TargetFeasibilityItem(
        role=target.role.value,
        price=target.price,
        source=target.source,
        conditional=target.conditional,
        declared_move_percentage=target.expected_move_percentage,
        derived_move_percentage=derived_move,
        net_move_percentage=net_move,
        declared_risk_multiple=target.risk_multiple,
        derived_gross_risk_multiple=derived_r,
        derived_net_risk_multiple=net_r,
        declared_geometry_consistent=consistent,
        on_correct_side=_target_on_correct_side(methodology, target),
        obstacle_price=None if obstacle is None else obstacle.obstacle_price,
        obstacle_relation=None if obstacle is None else obstacle.relation.value,
        obstacle_structure_kind=None if obstacle is None else obstacle.structure_kind,
        obstacle_source=None if obstacle is None else obstacle.source,
        clearance_buffer_percentage=(
            None if obstacle is None else obstacle.clearance_buffer_percentage
        ),
        room_to_obstacle_percentage=room_percentage,
        clear_room_proven=clear_room,
    )


def _validate_obstacle_evidence(
    methodology: MethodologySnapshot,
    evidence: tuple[TargetObstacleEvidence, ...],
) -> None:
    roles = [item.target_role for item in evidence]
    if len(set(roles)) != len(roles):
        raise ValueError("target obstacle evidence roles must be unique")
    target_roles = {target.role for target in methodology.targets}
    if any(role not in target_roles for role in roles):
        raise ValueError("target obstacle evidence must reference a canonical target role")


def _target_on_correct_side(
    methodology: MethodologySnapshot,
    target: TargetCandidate,
) -> bool | None:
    decision = methodology.selected_entry
    if methodology.direction is None or decision is None:
        return None
    entry = decision.opportunity
    if methodology.direction is TradeDirection.LONG:
        return target.price > entry.zone_high
    return target.price < entry.zone_low


__all__ = [
    "TargetFeasibilityItem",
    "TargetFeasibilitySemantics",
    "derive_target_feasibility_semantics",
    "target_feasibility_semantics_payload",
]
