"""Project existing setup geometry without fabricating unavailable methodology values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_setup_maturity import derive_setup_maturity
from apex.strategies.entry_status import EntryStatus


class ProjectedValueState(StrEnum):
    """Availability state for compatibility-projected geometry."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ProjectedValue:
    """One projected value with explicit availability and provenance."""

    value: object | None
    state: ProjectedValueState
    source: str
    reason: str

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.reason.strip():
            raise ValueError("projected value source and reason cannot be empty")
        if self.state is ProjectedValueState.AVAILABLE and self.value is None:
            raise ValueError("available projected values require a value")
        if self.state is not ProjectedValueState.AVAILABLE and self.value is not None:
            raise ValueError("unavailable projected values cannot carry a value")


@dataclass(frozen=True, slots=True)
class ProjectedEntryGeometry:
    """Compatibility entry geometry derived only from existing setup values."""

    zone_low: float
    zone_high: float
    ideal_entry: float
    current_price: float
    maximum_chase: float
    current_distance_percentage: float
    current_distance_atr: ProjectedValue
    confirmation_level: ProjectedValue
    entry_model: str
    execution_conditions_complete: bool
    expiry_bars: ProjectedValue


@dataclass(frozen=True, slots=True)
class ProjectedInvalidationGeometry:
    """Existing structural stop projected with unknown buffers left unavailable."""

    price: float
    rule: str
    structure: str
    failure_event: str
    volatility_buffer: ProjectedValue
    estimated_slippage: ProjectedValue


@dataclass(frozen=True, slots=True)
class ProjectedTargetGeometry:
    """Target geometry calculated from explicit setup prices only."""

    role: str
    price: float
    source: str
    expected_move_percentage: float
    risk_multiple: float
    conditional: bool


@dataclass(frozen=True, slots=True)
class ProjectedDurationGeometry:
    """Duration metadata that refuses to infer clock time from policy count."""

    hold_category: ProjectedValue
    expected_hold_min_seconds: ProjectedValue
    expected_hold_max_seconds: ProjectedValue
    expected_bars: ProjectedValue
    setup_expiry_bars: ProjectedValue
    expiry_reason: str


def project_setup_geometry(setup: DiscoverySetup) -> dict[str, Any]:
    """Return truthful compatibility geometry for a selected discovery setup.

    Existing prices and ratios are projected. ATR-normalized distance, volatility
    buffer, slippage, duration, and confirmation levels remain unavailable unless
    the selected setup explicitly supplies them through the canonical pipeline.
    """

    maturity = derive_setup_maturity(setup.strategy, setup.entry_status)
    entry = ProjectedEntryGeometry(
        zone_low=setup.entry.lower,
        zone_high=setup.entry.upper,
        ideal_entry=setup.entry.preferred,
        current_price=setup.entry.current_price,
        maximum_chase=setup.entry.maximum_chase_price,
        current_distance_percentage=(
            abs(setup.entry.current_price - setup.entry.preferred)
            / setup.entry.current_price
            * 100.0
        ),
        current_distance_atr=_unavailable(
            source="legacy discovery setup",
            reason="ATR distance is not present in the selected setup contract",
        ),
        confirmation_level=_unavailable(
            source="legacy discovery setup",
            reason="an explicit confirmation price is not present in the selected setup contract",
        ),
        entry_model=_entry_model(setup.entry_status),
        execution_conditions_complete=maturity.execution_conditions_complete,
        expiry_bars=_unavailable(
            source="legacy management policies",
            reason="policy count is not a valid substitute for setup expiry bars",
        ),
    )
    invalidation = ProjectedInvalidationGeometry(
        price=setup.stop_loss.price,
        rule="close",
        structure="; ".join(setup.stop_loss.rationale),
        failure_event="price closes beyond the existing structural stop",
        volatility_buffer=_unavailable(
            source="legacy stop geometry",
            reason="the stop contract does not expose a separate volatility buffer",
        ),
        estimated_slippage=_unavailable(
            source="execution metadata",
            reason="estimated slippage is not available in the selected setup contract",
        ),
    )
    targets = tuple(
        ProjectedTargetGeometry(
            role=_target_role(index, len(setup.take_profits)),
            price=target.price,
            source="; ".join(target.rationale),
            expected_move_percentage=(
                abs(target.price - setup.entry.preferred) / setup.entry.preferred * 100.0
            ),
            risk_multiple=target.risk_reward,
            conditional=index > 2,
        )
        for index, target in enumerate(setup.take_profits, start=1)
    )
    duration = ProjectedDurationGeometry(
        hold_category=_unavailable(
            source="legacy discovery setup",
            reason="holding category requires setup, timeframe, volatility, and target timing",
        ),
        expected_hold_min_seconds=_unavailable(
            source="legacy discovery setup",
            reason="minimum holding time is not present and is not inferred from policy count",
        ),
        expected_hold_max_seconds=_unavailable(
            source="legacy discovery setup",
            reason="maximum holding time is not present and is not inferred from policy count",
        ),
        expected_bars=_unavailable(
            source="legacy discovery setup",
            reason="expected bars require strategy-specific historical or structural timing",
        ),
        setup_expiry_bars=_unavailable(
            source="legacy management policies",
            reason="management policy count is not setup expiry",
        ),
        expiry_reason="duration and expiry remain deferred until canonical timing metadata exists",
    )
    return {
        "entry": _entry_payload(entry),
        "invalidation": _invalidation_payload(invalidation),
        "targets": [_target_payload(item) for item in targets],
        "duration": _duration_payload(duration),
        "projection_basis": "selected legacy setup compatibility",
        "fabricated_defaults_used": False,
    }


def _entry_model(status: EntryStatus) -> str:
    return {
        EntryStatus.READY_NOW: "immediate_entry",
        EntryStatus.AGGRESSIVE_NOW: "aggressive_entry",
        EntryStatus.PULLBACK_PREFERRED: "pullback_entry",
        EntryStatus.WATCH_NEAR_ENTRY: "developing_future_entry",
        EntryStatus.LATE_OR_CHASING: "preferred_nearby_entry",
        EntryStatus.INVALIDATED: "developing_future_entry",
    }[status]


def _target_role(index: int, count: int) -> str:
    if index == 1:
        return "tp1"
    if index == 2:
        return "tp2"
    if index == 3 and count == 3:
        return "tp3"
    return "runner"


def _unavailable(*, source: str, reason: str) -> ProjectedValue:
    return ProjectedValue(
        value=None,
        state=ProjectedValueState.UNAVAILABLE,
        source=source,
        reason=reason,
    )


def _projected_value_payload(value: ProjectedValue) -> dict[str, object | None]:
    return {
        "value": value.value,
        "state": value.state.value,
        "source": value.source,
        "reason": value.reason,
    }


def _entry_payload(entry: ProjectedEntryGeometry) -> dict[str, Any]:
    return {
        "zone_low": entry.zone_low,
        "zone_high": entry.zone_high,
        "ideal_entry": entry.ideal_entry,
        "current_price": entry.current_price,
        "maximum_chase": entry.maximum_chase,
        "current_distance_percentage": entry.current_distance_percentage,
        "current_distance_atr": _projected_value_payload(entry.current_distance_atr),
        "confirmation_level": _projected_value_payload(entry.confirmation_level),
        "entry_model": entry.entry_model,
        "execution_conditions_complete": entry.execution_conditions_complete,
        "expiry_bars": _projected_value_payload(entry.expiry_bars),
    }


def _invalidation_payload(invalidation: ProjectedInvalidationGeometry) -> dict[str, Any]:
    return {
        "price": invalidation.price,
        "rule": invalidation.rule,
        "structure": invalidation.structure,
        "failure_event": invalidation.failure_event,
        "volatility_buffer": _projected_value_payload(invalidation.volatility_buffer),
        "estimated_slippage": _projected_value_payload(invalidation.estimated_slippage),
    }


def _target_payload(target: ProjectedTargetGeometry) -> dict[str, Any]:
    return {
        "role": target.role,
        "price": target.price,
        "source": target.source,
        "expected_move_percentage": target.expected_move_percentage,
        "risk_multiple": target.risk_multiple,
        "conditional": target.conditional,
    }


def _duration_payload(duration: ProjectedDurationGeometry) -> dict[str, Any]:
    return {
        "hold_category": _projected_value_payload(duration.hold_category),
        "expected_hold_min_seconds": _projected_value_payload(
            duration.expected_hold_min_seconds
        ),
        "expected_hold_max_seconds": _projected_value_payload(
            duration.expected_hold_max_seconds
        ),
        "expected_bars": _projected_value_payload(duration.expected_bars),
        "setup_expiry_bars": _projected_value_payload(duration.setup_expiry_bars),
        "expiry_reason": duration.expiry_reason,
    }


__all__ = [
    "ProjectedDurationGeometry",
    "ProjectedEntryGeometry",
    "ProjectedInvalidationGeometry",
    "ProjectedTargetGeometry",
    "ProjectedValue",
    "ProjectedValueState",
    "project_setup_geometry",
]
