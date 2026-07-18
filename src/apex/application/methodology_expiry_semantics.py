"""Interpret setup and entry expiry without inventing elapsed-bar state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity


@dataclass(frozen=True, slots=True)
class ExpirySemantics:
    """Public interpretation of setup lifetime and expiry evidence."""

    setup_expiry_bars: int | None
    minimum_entry_expiry_bars: int | None
    maximum_entry_expiry_bars: int | None
    expiry_reason: str | None
    late_or_missed: bool
    structurally_failed: bool
    elapsed_bars_available: bool
    expired_proven: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_expiry_semantics(methodology: MethodologySnapshot) -> ExpirySemantics:
    """Describe expiry using declared budgets and canonical maturity only."""

    duration = methodology.duration
    entry_expiry_values = tuple(item.expiry_bars for item in methodology.entry_opportunities)
    maturity = methodology.setup_maturity
    late_or_missed = maturity in {
        SetupMaturity.ENTRY_LATE,
        SetupMaturity.ENTRY_MISSED,
    }
    structurally_failed = maturity in {
        SetupMaturity.INVALIDATED,
        SetupMaturity.PATTERN_FAILED,
    }

    if structurally_failed:
        interpretation = "the setup has structurally failed; expiry is no longer the governing issue"
    elif late_or_missed:
        interpretation = "canonical maturity marks the original opportunity as late or missed"
    elif duration is None and not entry_expiry_values:
        interpretation = "no canonical setup or entry expiry budget is available"
    else:
        interpretation = (
            "expiry budgets are available, but elapsed bars are not recorded so expiration "
            "must not be inferred"
        )

    return ExpirySemantics(
        setup_expiry_bars=None if duration is None else duration.setup_expiry_bars,
        minimum_entry_expiry_bars=min(entry_expiry_values) if entry_expiry_values else None,
        maximum_entry_expiry_bars=max(entry_expiry_values) if entry_expiry_values else None,
        expiry_reason=None if duration is None else duration.expiry_reason,
        late_or_missed=late_or_missed,
        structurally_failed=structurally_failed,
        elapsed_bars_available=False,
        expired_proven=late_or_missed or structurally_failed,
        interpretation=interpretation,
        limitations=(
            "expiry bars are a declared validity budget, not a wall-clock promise",
            "elapsed bars are unavailable and must not be guessed from decision timestamps",
            "moving away from an entry zone is not automatically the same as expiry",
            "late, missed, invalidated, and pattern-failed states remain distinct",
        ),
    )


def expiry_semantics_payload(semantics: ExpirySemantics) -> dict[str, Any]:
    """Serialize setup and entry expiry interpretation."""

    return {
        "setup_expiry_bars": semantics.setup_expiry_bars,
        "minimum_entry_expiry_bars": semantics.minimum_entry_expiry_bars,
        "maximum_entry_expiry_bars": semantics.maximum_entry_expiry_bars,
        "expiry_reason": semantics.expiry_reason,
        "late_or_missed": semantics.late_or_missed,
        "structurally_failed": semantics.structurally_failed,
        "elapsed_bars_available": semantics.elapsed_bars_available,
        "expired_proven": semantics.expired_proven,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ExpirySemantics",
    "derive_expiry_semantics",
    "expiry_semantics_payload",
]
