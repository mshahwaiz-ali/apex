"""Interpret canonical market usability without treating it as trade confidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import MarketUsabilityState
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class MarketUsabilitySemantics:
    """Public interpretation of market-data and execution-quality usability."""

    available: bool
    state: str | None
    score: float | None
    execution_usable: bool
    caution_required: bool
    execution_blocked: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    interpretation: str
    limitations: tuple[str, ...]


def derive_market_usability_semantics(
    methodology: MethodologySnapshot,
) -> MarketUsabilitySemantics:
    """Describe market usability without converting it into setup confidence."""

    assessment = methodology.market_usability
    if assessment is None:
        return MarketUsabilitySemantics(
            available=False,
            state=None,
            score=None,
            execution_usable=False,
            caution_required=False,
            execution_blocked=False,
            reasons=(),
            warnings=(),
            missing_inputs=(),
            interpretation=(
                "market usability is unavailable; liquidity, spread, freshness, and "
                "execution quality must not be assumed"
            ),
            limitations=_limitations(),
        )

    execution_usable = assessment.state in {
        MarketUsabilityState.USABLE,
        MarketUsabilityState.USABLE_WITH_CAUTION,
    }
    caution_required = assessment.state is MarketUsabilityState.USABLE_WITH_CAUTION
    execution_blocked = assessment.state in {
        MarketUsabilityState.UNUSABLE,
        MarketUsabilityState.DATA_INCOMPLETE,
    }
    if assessment.state is MarketUsabilityState.USABLE:
        interpretation = "market execution quality is currently usable"
    elif assessment.state is MarketUsabilityState.USABLE_WITH_CAUTION:
        interpretation = (
            "market remains usable, but explicit execution-quality cautions must remain visible"
        )
    elif assessment.state is MarketUsabilityState.UNUSABLE:
        interpretation = "market execution quality is unusable and should block execution"
    else:
        interpretation = (
            "market usability cannot be established because required execution-quality "
            "data is incomplete"
        )

    return MarketUsabilitySemantics(
        available=True,
        state=assessment.state.value,
        score=assessment.score,
        execution_usable=execution_usable,
        caution_required=caution_required,
        execution_blocked=execution_blocked,
        reasons=assessment.reasons,
        warnings=assessment.warnings,
        missing_inputs=assessment.missing_inputs,
        interpretation=interpretation,
        limitations=_limitations(),
    )


def market_usability_semantics_payload(
    semantics: MarketUsabilitySemantics,
) -> dict[str, Any]:
    """Serialize market-usability interpretation for public output."""

    return {
        "available": semantics.available,
        "state": semantics.state,
        "score": semantics.score,
        "execution_usable": semantics.execution_usable,
        "caution_required": semantics.caution_required,
        "execution_blocked": semantics.execution_blocked,
        "reasons": list(semantics.reasons),
        "warnings": list(semantics.warnings),
        "missing_inputs": list(semantics.missing_inputs),
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


def _limitations() -> tuple[str, ...]:
    return (
        "market-usability score is not trade confidence or win probability",
        "usable market conditions do not make an otherwise invalid setup executable",
        "missing spread, tick-size, step-size, or confidence data remains missing",
        "execution usability is evaluated before strategy quality and entry timing",
    )


__all__ = [
    "MarketUsabilitySemantics",
    "derive_market_usability_semantics",
    "market_usability_semantics_payload",
]
