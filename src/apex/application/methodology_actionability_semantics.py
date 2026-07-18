"""Resolve authoritative actionability without trusting legacy status wording alone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity


@dataclass(frozen=True, slots=True)
class ActionabilitySemantics:
    """Public actionability status derived from canonical methodology state."""

    legacy_status: str | None
    canonical_maturity: str | None
    execution_ready: bool
    actionability: str
    legacy_status_authoritative: bool
    interpretation: str


def derive_actionability_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
) -> ActionabilitySemantics:
    """Classify actionability with hard blockers and geometry taking precedence."""

    legacy_status = None if setup is None else setup.entry_status.value
    maturity = methodology.setup_maturity
    blocked = bool(methodology.hard_blockers)
    execution_ready = (
        methodology.executable and maturity is SetupMaturity.ENTRY_AVAILABLE and not blocked
    )

    if blocked:
        actionability = "blocked"
        interpretation = "explicit methodology hard blockers prevent execution"
    elif maturity is SetupMaturity.INVALIDATED or maturity is SetupMaturity.PATTERN_FAILED:
        actionability = "invalidated"
        interpretation = "the setup has failed or become structurally invalid"
    elif maturity in {SetupMaturity.ENTRY_LATE, SetupMaturity.ENTRY_MISSED}:
        actionability = "late_or_missed"
        interpretation = "the original entry opportunity is late or already missed"
    elif execution_ready and maturity is SetupMaturity.ENTRY_AVAILABLE:
        actionability = "entry_available"
        interpretation = (
            "canonical entry, invalidation, targets, and required conditions are complete"
        )
    elif maturity in {
        SetupMaturity.RETEST_PENDING,
        SetupMaturity.RECLAIM_PENDING,
        SetupMaturity.CONFIRMATION_PENDING_CLOSE,
        SetupMaturity.TRIGGER_PROVISIONAL,
        SetupMaturity.SETUP_CONFIRMED,
    }:
        actionability = "developing"
        interpretation = "the setup is valid but one or more execution conditions remain pending"
    elif maturity is SetupMaturity.PATTERN_DEVELOPING:
        actionability = "watch"
        interpretation = "the pattern is developing and is not an executable trade"
    elif setup is None:
        actionability = "no_trade"
        interpretation = "no selected setup exists"
    else:
        actionability = "not_executable"
        interpretation = (
            "legacy setup information exists without complete canonical execution state"
        )

    return ActionabilitySemantics(
        legacy_status=legacy_status,
        canonical_maturity=None if maturity is None else maturity.value,
        execution_ready=execution_ready,
        actionability=actionability,
        legacy_status_authoritative=False,
        interpretation=interpretation,
    )


def actionability_semantics_payload(
    semantics: ActionabilitySemantics,
) -> dict[str, Any]:
    """Serialize authoritative actionability wording for public output."""

    return {
        "legacy_status": semantics.legacy_status,
        "canonical_maturity": semantics.canonical_maturity,
        "execution_ready": semantics.execution_ready,
        "actionability": semantics.actionability,
        "legacy_status_authoritative": semantics.legacy_status_authoritative,
        "interpretation": semantics.interpretation,
    }


__all__ = [
    "ActionabilitySemantics",
    "actionability_semantics_payload",
    "derive_actionability_semantics",
]
