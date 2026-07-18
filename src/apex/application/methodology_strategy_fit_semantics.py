"""Interpret selected-strategy fit without inventing an unavailable eligibility matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class StrategyFitSemantics:
    """Public verdict for selected strategy versus canonical market state."""

    selected_strategy: str | None
    primary_state: str | None
    explicit_mismatch_blocker: bool
    direct_opposition_blocker: bool
    mild_conflict_penalty: bool
    fit_status: str
    eligibility_matrix_available: bool
    interpretation: str


def derive_strategy_fit_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
) -> StrategyFitSemantics:
    """Resolve only the fit information explicitly present in methodology state."""

    hard_codes = {item.code.value for item in methodology.hard_blockers}
    soft_codes = {item.code.value for item in methodology.soft_penalties}
    mismatch = "wrong_strategy_for_state" in hard_codes
    direct = "direct_structural_opposition" in hard_codes
    mild = "mild_htf_conflict" in soft_codes
    state = methodology.market_state

    if setup is None:
        fit_status = "no_selected_strategy"
        interpretation = "no selected setup exists, so strategy fit is not applicable"
    elif mismatch:
        fit_status = "incompatible"
        interpretation = "an explicit wrong-strategy-for-state hard blocker is present"
    elif direct:
        fit_status = "structurally_opposed"
        interpretation = (
            "direct structural opposition prevents the selected strategy from executing"
        )
    elif state is None:
        fit_status = "unverified"
        interpretation = (
            "market state is unavailable, so selected-strategy compatibility cannot be verified"
        )
    elif mild:
        fit_status = "compatible_with_penalty"
        interpretation = (
            "no explicit incompatibility blocker is present, but mild higher-timeframe "
            "conflict reduces quality"
        )
    else:
        fit_status = "no_explicit_conflict"
        interpretation = (
            "no explicit strategy-state mismatch is recorded; full eligibility remains unavailable"
        )

    return StrategyFitSemantics(
        selected_strategy=None if setup is None else setup.strategy.value,
        primary_state=None if state is None else state.primary.value,
        explicit_mismatch_blocker=mismatch,
        direct_opposition_blocker=direct,
        mild_conflict_penalty=mild,
        fit_status=fit_status,
        eligibility_matrix_available=False,
        interpretation=interpretation,
    )


def strategy_fit_semantics_payload(semantics: StrategyFitSemantics) -> dict[str, Any]:
    """Serialize the explicit strategy-fit verdict."""

    return {
        "selected_strategy": semantics.selected_strategy,
        "primary_state": semantics.primary_state,
        "explicit_mismatch_blocker": semantics.explicit_mismatch_blocker,
        "direct_opposition_blocker": semantics.direct_opposition_blocker,
        "mild_conflict_penalty": semantics.mild_conflict_penalty,
        "fit_status": semantics.fit_status,
        "eligibility_matrix_available": semantics.eligibility_matrix_available,
        "interpretation": semantics.interpretation,
    }


__all__ = [
    "StrategyFitSemantics",
    "derive_strategy_fit_semantics",
    "strategy_fit_semantics_payload",
]
