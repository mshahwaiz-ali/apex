"""Interpret candle confirmation requirements from explicit physical source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_source_data_contracts import SourceCandleMetadata
from apex.application.methodology_strategy_contracts import ConfirmationPolicy, SetupMaturity


@dataclass(frozen=True, slots=True)
class ConfirmationSourceSemantics:
    """Public interpretation of policy, maturity, and physical source-candle state."""

    policy_available: bool
    confirmation_policy: str | None
    close_required: bool
    intrabar_allowed: bool
    confirmation_complete: bool
    provisional_signal: bool
    physical_candle_state_available: bool
    source_id: str | None
    source_symbol: str | None
    source_timeframe: str | None
    source_provider: str | None
    source_opened_at: str | None
    source_closes_at: str | None
    source_observed_at: str | None
    source_is_closed: bool | None
    closed_candle_proven: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_confirmation_source_semantics(
    methodology: MethodologySnapshot,
    source_candle: SourceCandleMetadata | None = None,
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
    physical_available = source_candle is not None
    closed_proven = bool(source_candle is not None and source_candle.is_closed)

    if policy is None:
        interpretation = (
            "confirmation policy is unavailable; physical source state is reported separately "
            "and must not be converted into methodology confirmation"
        )
    elif close_required and not confirmation_complete:
        interpretation = "close confirmation is required and remains pending"
    elif provisional_signal:
        interpretation = (
            "the current signal is provisional and must not be presented as fully confirmed"
        )
    elif close_required and confirmation_complete and closed_proven:
        interpretation = (
            "close confirmation is complete and the recorded physical source candle is closed"
        )
    elif close_required and confirmation_complete:
        interpretation = (
            "policy and maturity indicate close confirmation was satisfied, but physical candle "
            "closure is not independently proven"
        )
    elif intrabar_allowed and source_candle is not None and not source_candle.is_closed:
        interpretation = (
            "intrabar confirmation is permitted and the recorded source candle remains open"
        )
    elif intrabar_allowed:
        interpretation = (
            "intrabar or lower-timeframe confirmation is permitted and remains distinct from "
            "closed-candle proof"
        )
    else:
        interpretation = "canonical confirmation requirements are complete"

    limitations = [
        "confirmation completion does not by itself identify or prove a physical candle",
        "intrabar evidence must not masquerade as closed-candle confirmation",
        "close-required setups remain non-executable while confirmation is pending",
    ]
    if source_candle is None:
        limitations.append(
            "missing candle identity, timestamps, and closure flag remain unavailable"
        )

    return ConfirmationSourceSemantics(
        policy_available=policy is not None,
        confirmation_policy=None if policy is None else policy.value,
        close_required=close_required,
        intrabar_allowed=intrabar_allowed,
        confirmation_complete=confirmation_complete,
        provisional_signal=provisional_signal,
        physical_candle_state_available=physical_available,
        source_id=None if source_candle is None else source_candle.source_id,
        source_symbol=None if source_candle is None else source_candle.symbol,
        source_timeframe=None if source_candle is None else source_candle.timeframe,
        source_provider=None if source_candle is None else source_candle.provider,
        source_opened_at=(None if source_candle is None else source_candle.opened_at.isoformat()),
        source_closes_at=(None if source_candle is None else source_candle.closes_at.isoformat()),
        source_observed_at=(
            None if source_candle is None else source_candle.observed_at.isoformat()
        ),
        source_is_closed=None if source_candle is None else source_candle.is_closed,
        closed_candle_proven=closed_proven,
        interpretation=interpretation,
        limitations=tuple(limitations),
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
        "source_id": semantics.source_id,
        "source_symbol": semantics.source_symbol,
        "source_timeframe": semantics.source_timeframe,
        "source_provider": semantics.source_provider,
        "source_opened_at": semantics.source_opened_at,
        "source_closes_at": semantics.source_closes_at,
        "source_observed_at": semantics.source_observed_at,
        "source_is_closed": semantics.source_is_closed,
        "closed_candle_proven": semantics.closed_candle_proven,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ConfirmationSourceSemantics",
    "confirmation_source_semantics_payload",
    "derive_confirmation_source_semantics",
]
