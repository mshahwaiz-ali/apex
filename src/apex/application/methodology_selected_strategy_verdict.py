"""Summarize methodology enforcement for the selected discovery strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.strategies.strategy_types import StrategyType


class SelectedStrategyVerdictState(StrEnum):
    NO_SETUP = "no_setup"
    ALLOWED = "allowed"
    SUPPRESSED = "suppressed"
    DEFERRED = "deferred"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SelectedStrategyVerdict:
    state: SelectedStrategyVerdictState
    strategy: StrategyType | None
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes or not self.reasons:
            raise ValueError("selected strategy verdict requires reasons")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("selected strategy verdict reason codes must be unique")
        if self.state is SelectedStrategyVerdictState.NO_SETUP and self.strategy is not None:
            raise ValueError("no-setup verdict cannot identify a strategy")
        if self.state is not SelectedStrategyVerdictState.NO_SETUP and self.strategy is None:
            raise ValueError("strategy verdict requires a selected strategy")


def derive_selected_strategy_verdict(
    *,
    selected_strategy: StrategyType | None,
    decisions: tuple[StrategyEnforcementDecision, ...],
) -> SelectedStrategyVerdict:
    """Return one concise verdict without mutating routing or selection."""

    if selected_strategy is None:
        return SelectedStrategyVerdict(
            state=SelectedStrategyVerdictState.NO_SETUP,
            strategy=None,
            reason_codes=("NO_SELECTED_SETUP",),
            reasons=("no discovery setup was selected",),
        )

    decision = next(
        (item for item in decisions if item.strategy is selected_strategy),
        None,
    )
    if decision is None:
        return SelectedStrategyVerdict(
            state=SelectedStrategyVerdictState.UNAVAILABLE,
            strategy=selected_strategy,
            reason_codes=("SELECTED_STRATEGY_DECISION_UNAVAILABLE",),
            reasons=(f"no methodology enforcement decision exists for {selected_strategy.value}",),
        )

    state = {
        StrategyEnforcementAction.ALLOW: SelectedStrategyVerdictState.ALLOWED,
        StrategyEnforcementAction.SUPPRESS: SelectedStrategyVerdictState.SUPPRESSED,
        StrategyEnforcementAction.DEFER: SelectedStrategyVerdictState.DEFERRED,
    }[decision.action]
    return SelectedStrategyVerdict(
        state=state,
        strategy=selected_strategy,
        reason_codes=decision.reason_codes,
        reasons=decision.reasons,
    )


def selected_strategy_verdict_payload(
    verdict: SelectedStrategyVerdict,
) -> dict[str, Any]:
    return {
        "state": verdict.state.value,
        "strategy": None if verdict.strategy is None else verdict.strategy.value,
        "reason_codes": list(verdict.reason_codes),
        "reasons": list(verdict.reasons),
    }


__all__ = [
    "SelectedStrategyVerdict",
    "SelectedStrategyVerdictState",
    "derive_selected_strategy_verdict",
    "selected_strategy_verdict_payload",
]
