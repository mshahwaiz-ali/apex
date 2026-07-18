"""Interpret target feasibility without imposing a universal reward threshold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import TargetCandidate
from apex.application.methodology_snapshot import MethodologySnapshot
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
    declared_risk_multiple: float
    derived_gross_risk_multiple: float | None
    declared_geometry_consistent: bool | None
    on_correct_side: bool | None


@dataclass(frozen=True, slots=True)
class TargetFeasibilitySemantics:
    """Truthful target geometry, provenance, and unavailable feasibility evidence."""

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
    net_reward_geometry_available: bool
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
) -> TargetFeasibilitySemantics:
    """Derive gross target geometry while preserving unavailable costs and obstacles."""

    decision = methodology.selected_entry
    invalidation = methodology.invalidation
    opportunity = None if decision is None else decision.opportunity
    entry = None if opportunity is None else opportunity.ideal_entry
    risk_distance = (
        None
        if entry is None or invalidation is None
        else abs(entry - invalidation.price)
    )
    gross_available = risk_distance is not None and risk_distance > 0.0
    items = tuple(
        _target_item(
            target,
            methodology=methodology,
            entry=entry,
            risk_distance=risk_distance,
        )
        for target in methodology.targets
    )
    directional_results = tuple(
        item.on_correct_side for item in items if item.on_correct_side is not None
    )
    directionally_validated = bool(items) and len(directional_results) == len(items)
    all_correct = all(directional_results) if directionally_validated else None

    if not methodology.targets:
        interpretation = "no canonical target candidates are available"
    elif not gross_available:
        interpretation = (
            "canonical targets exist, but gross reward geometry cannot be derived until an "
            "authoritative selected entry and structural invalidation are both available"
        )
    elif not directionally_validated:
        interpretation = (
            "gross reward geometry is available, but canonical direction is unavailable so "
            "target-side correctness cannot be proven"
        )
    else:
        interpretation = (
            "gross target distance, directional side, and R-multiple magnitudes are derived from "
            "canonical geometry; no universal minimum R:R is imposed"
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
        costs_available=False,
        net_reward_geometry_available=False,
        obstacle_room_proven=None,
        directionally_validated=directionally_validated,
        all_targets_on_correct_side=all_correct,
        universal_minimum_risk_reward_applied=False,
        interpretation=interpretation,
        limitations=(
            "fees, funding, spread, and target-exit slippage are unavailable, so net reward geometry is not claimed",
            "target source text does not prove clear room before opposing structure",
            "declared and derived R multiples may differ because legacy or upstream calculations may use different entry or cost assumptions",
            "strategy-specific expectancy is required before judging whether any R multiple is sufficient",
        ),
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
                "declared_risk_multiple": item.declared_risk_multiple,
                "derived_gross_risk_multiple": item.derived_gross_risk_multiple,
                "declared_geometry_consistent": item.declared_geometry_consistent,
                "on_correct_side": item.on_correct_side,
            }
            for item in semantics.targets
        ],
        "costs_available": semantics.costs_available,
        "net_reward_geometry_available": semantics.net_reward_geometry_available,
        "obstacle_room_proven": semantics.obstacle_room_proven,
        "directionally_validated": semantics.directionally_validated,
        "all_targets_on_correct_side": semantics.all_targets_on_correct_side,
        "universal_minimum_risk_reward_applied": (
            semantics.universal_minimum_risk_reward_applied
        ),
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _target_item(
    target: TargetCandidate,
    *,
    methodology: MethodologySnapshot,
    entry: float | None,
    risk_distance: float | None,
) -> TargetFeasibilityItem:
    derived_move = None if entry is None else abs(target.price - entry) / entry * 100.0
    derived_r = (
        None
        if entry is None or risk_distance is None or risk_distance <= 0.0
        else abs(target.price - entry) / risk_distance
    )
    consistent = (
        None
        if derived_r is None
        else abs(derived_r - target.risk_multiple) <= max(0.05, derived_r * 0.05)
    )
    return TargetFeasibilityItem(
        role=target.role.value,
        price=target.price,
        source=target.source,
        conditional=target.conditional,
        declared_move_percentage=target.expected_move_percentage,
        derived_move_percentage=derived_move,
        declared_risk_multiple=target.risk_multiple,
        derived_gross_risk_multiple=derived_r,
        declared_geometry_consistent=consistent,
        on_correct_side=_target_on_correct_side(methodology, target),
    )


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
