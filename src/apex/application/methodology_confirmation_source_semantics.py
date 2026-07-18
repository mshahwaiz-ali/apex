"""Interpret candle confirmation requirements without inventing source-state metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import ConfirmationPolicy, SetupMaturity


@dataclass(frozen=True, slots=True)
class ConfirmationSourceSemantics:
    """Public interpretation of policy, maturity, and unresolved source-candle state."""

    policy_available: bool
    confirmation_policy: str | None
    close_required: bool
    intrabar_allowed: bool
    confirmation_complete: bool
    provisional_signal: bool
    physical_candle_state_available: bool
    closed_candle_proven: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_confirmation_source_semantics(
    methodology: MethodologySnapshot,
) -> ConfirmationSourceSemantics:
    """Describe confirmation truth without treating maturity as candle metadata."""

    policy = methodology.confirmation_policy
    maturity = methodology.setup_maturity
    close_required = policy is ConfirmationPolicy.CLOSE_REQUIRED
    intrabar_allowed = policy in {
        ConfirmationPolicy.INTRABAR_ALLOWED,
        ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
    }
    confirmation_complete = maturity in {
        SetupMaturity.SETUP_CONFIRMED,
        SetupMaturity.ENTRY_AVAILABLE,
        SetupMaturity.ENTRY_LATE,
        SetupMaturity.ENTRY_MISSED,
    }
    provisional_signal = maturity in {
        SetupMaturity.TRIGGER_PROVISIONAL,
        SetupMaturity.CONFIRMATION_PENDING_CLOSE,
    }

    if policy is None:
        interpretation = (
            "confirmation source is unavailable; active-candle or closed-candle status must "
            "not be inferred"
        )
    elif close_required and not confirmation_complete:
        interpretation = "close confirmation is required and remains pending"
    elif provisional_signal:
        interpretation = (
            "the current signal is provisional and must not be presented as fully confirmed"
        )
    elif close_required and confirmation_complete:
        interpretation = (
            "policy and setup maturity indicate that close confirmation was satisfied, but the "
            "physical source candle and its closed state are not independently recorded"
        )
    elif intrabar_allowed:
        interpretation = (
            "intrabar or lower-timeframe confirmation is permitted by policy and remains "
            "distinct from physical closed-candle proof"
        )
    else:
        interpretation = "canonical confirmation requirements are complete"

    return ConfirmationSourceSemantics(
        policy_available=policy is not None,
        confirmation_policy=None if policy is None else policy.value,
        close_required=close_required,
        intrabar_allowed=intrabar_allowed,
        confirmation_complete=confirmation_complete,
        provisional_signal=provisional_signal,
        physical_candle_state_available=False,
        closed_candle_proven=False,
        interpretation=interpretation,
        limitations=(
            "policy and maturity do not identify the physical source candle",
            "confirmation completion is not equivalent to independently proven candle closure",
            "intrabar evidence must not masquerade as closed-candle confirmation",
            "close-required setups remain non-executable while confirmation is pending",
            "missing candle timestamps and closure flags remain unavailable rather than assumed",
        ),
    )


def confirmation_source_semantics_payload(
    semantics: ConfirmationSourceSemantics,
) -> dict[str, Any]:
    """Serialize confirmation-source interpretation."""

    return {
        "policy_available": semantics.policy_available,
        "confirmation_policy": semantics.confirmation_policy,
        "close_required": semantics.close_required,
        "intrabar_allowed": semantics.intrabar_allowed,
        "confirmation_complete": semantics.confirmation_complete,
        "provisional_signal": semantics.provisional_signal,
        "physical_candle_state_available": semantics.physical_candle_state_available,
        "closed_candle_proven": semantics.closed_candle_proven,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ConfirmationSourceSemantics",
    "confirmation_source_semantics_payload",
    "derive_confirmation_source_semantics",
]
