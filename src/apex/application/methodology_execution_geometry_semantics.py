"""Interpret entry and invalidation geometry without overstating execution readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ExecutionGeometrySemantics:
    """Truthful execution interpretation for native and compatibility geometry."""

    setup_available: bool
    canonical_entry_available: bool
    canonical_invalidation_available: bool
    compatibility_entry_available: bool
    compatibility_stop_available: bool
    execution_ready: bool
    geometry_authoritative: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_execution_geometry_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
    *,
    native_methodology_available: bool,
) -> ExecutionGeometrySemantics:
    """Separate legacy price geometry from canonical execution completeness."""

    canonical_entry_available = bool(methodology.entry_opportunities)
    canonical_invalidation_available = methodology.invalidation is not None
    compatibility_entry_available = setup is not None
    compatibility_stop_available = setup is not None
    execution_ready = methodology.executable
    geometry_authoritative = (
        native_methodology_available
        and canonical_entry_available
        and canonical_invalidation_available
    )

    if execution_ready:
        interpretation = (
            "canonical entry, invalidation, and target geometry are complete and no hard "
            "methodology blocker is present"
        )
    elif setup is None:
        interpretation = "no selected setup exists, so execution geometry is unavailable"
    elif not canonical_entry_available or not canonical_invalidation_available:
        interpretation = (
            "legacy entry and stop prices are visible for compatibility, but canonical "
            "execution geometry remains incomplete"
        )
    else:
        interpretation = (
            "canonical geometry exists but another methodology condition prevents execution"
        )

    return ExecutionGeometrySemantics(
        setup_available=setup is not None,
        canonical_entry_available=canonical_entry_available,
        canonical_invalidation_available=canonical_invalidation_available,
        compatibility_entry_available=compatibility_entry_available,
        compatibility_stop_available=compatibility_stop_available,
        execution_ready=execution_ready,
        geometry_authoritative=geometry_authoritative,
        interpretation=interpretation,
        limitations=(
            "a legacy entry zone is not automatically an executable canonical opportunity",
            "a legacy stop price does not prove touch, wick, or close invalidation semantics",
            "missing volatility buffer and slippage remain unavailable rather than zero",
            "confirmation and maturity requirements take precedence over proximity to entry",
        ),
    )


def execution_geometry_semantics_payload(
    semantics: ExecutionGeometrySemantics,
) -> dict[str, Any]:
    """Serialize execution-geometry interpretation for public output."""

    return {
        "setup_available": semantics.setup_available,
        "canonical_entry_available": semantics.canonical_entry_available,
        "canonical_invalidation_available": semantics.canonical_invalidation_available,
        "compatibility_entry_available": semantics.compatibility_entry_available,
        "compatibility_stop_available": semantics.compatibility_stop_available,
        "execution_ready": semantics.execution_ready,
        "geometry_authoritative": semantics.geometry_authoritative,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ExecutionGeometrySemantics",
    "derive_execution_geometry_semantics",
    "execution_geometry_semantics_payload",
]
