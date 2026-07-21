"""Derive shadow routing decisions from methodology strategy eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_strategy_evaluation import (
    StrategyEligibilityEvaluation,
    StrategyEligibilityState,
)
from apex.strategies.strategy_types import StrategyType


class StrategyEnforcementAction(StrEnum):
    ALLOW = "allow"
    SUPPRESS = "suppress"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class StrategyEnforcementDecision:
    strategy: StrategyType
    action: StrategyEnforcementAction
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_codes or not self.reasons:
            raise ValueError("strategy enforcement decision requires reasons")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("strategy enforcement reason codes must be unique")
        if self.candidate_id is not None and not self.candidate_id.strip():
            raise ValueError("candidate-specific enforcement identity cannot be empty")


def derive_strategy_enforcement(
    evaluation: StrategyEligibilityEvaluation,
    *,
    candidate_id: str | None = None,
) -> StrategyEnforcementDecision:
    """Translate one eligibility result into a non-mutating routing decision."""

    if evaluation.state in {
        StrategyEligibilityState.COMPATIBLE,
        StrategyEligibilityState.COMPATIBLE_WITH_CONSTRAINTS,
    }:
        return StrategyEnforcementDecision(
            strategy=evaluation.strategy,
            action=StrategyEnforcementAction.ALLOW,
            reason_codes=(
                "METHODOLOGY_COMPATIBLE_WITH_CONSTRAINTS"
                if evaluation.state is StrategyEligibilityState.COMPATIBLE_WITH_CONSTRAINTS
                else "METHODOLOGY_COMPATIBLE",
            ),
            reasons=evaluation.reasons,
            candidate_id=candidate_id,
        )
    if evaluation.state is StrategyEligibilityState.PROHIBITED_STATE:
        return StrategyEnforcementDecision(
            strategy=evaluation.strategy,
            action=StrategyEnforcementAction.SUPPRESS,
            reason_codes=("METHODOLOGY_PROHIBITED_STATE",),
            reasons=evaluation.reasons,
            candidate_id=candidate_id,
        )
    if evaluation.state is StrategyEligibilityState.INCOMPATIBLE_STATE:
        return StrategyEnforcementDecision(
            strategy=evaluation.strategy,
            action=StrategyEnforcementAction.SUPPRESS,
            reason_codes=("METHODOLOGY_INCOMPATIBLE_STATE",),
            reasons=evaluation.reasons,
            candidate_id=candidate_id,
        )
    return StrategyEnforcementDecision(
        strategy=evaluation.strategy,
        action=StrategyEnforcementAction.DEFER,
        reason_codes=("METHODOLOGY_METADATA_INCOMPLETE",),
        reasons=evaluation.reasons,
        candidate_id=candidate_id,
    )


def derive_strategy_enforcement_registry(
    evaluations: tuple[StrategyEligibilityEvaluation, ...],
) -> tuple[StrategyEnforcementDecision, ...]:
    return tuple(derive_strategy_enforcement(item) for item in evaluations)


def strategy_enforcement_payload(
    decision: StrategyEnforcementDecision,
) -> dict[str, Any]:
    return {
        "candidate_id": decision.candidate_id,
        "strategy": decision.strategy.value,
        "action": decision.action.value,
        "reason_codes": list(decision.reason_codes),
        "reasons": list(decision.reasons),
    }


__all__ = [
    "StrategyEnforcementAction",
    "StrategyEnforcementDecision",
    "derive_strategy_enforcement",
    "derive_strategy_enforcement_registry",
    "strategy_enforcement_payload",
]
