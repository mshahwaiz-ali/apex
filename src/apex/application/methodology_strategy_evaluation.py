"""Evaluate strategy eligibility against canonical methodology state and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_contracts import EvidenceFamily, EvidenceObservation
from apex.application.methodology_opportunity_context import HoldingHorizon, OpportunityLane
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_registry import strategy_eligibility
from apex.strategies.contracts import TradeDirection
from apex.strategies.strategy_types import StrategyType


class StrategyEligibilityState(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE_STATE = "incompatible_state"
    PROHIBITED_STATE = "prohibited_state"
    COMPATIBLE_WITH_CONSTRAINTS = "compatible_with_constraints"
    INSUFFICIENT_EVIDENCE_METADATA = "insufficient_evidence_metadata"


@dataclass(frozen=True, slots=True)
class StrategyEligibilityEvaluation:
    strategy: StrategyType
    state: StrategyEligibilityState
    market_state: PrimaryMarketState | None
    present_evidence: tuple[EvidenceFamily, ...]
    missing_mandatory_evidence: tuple[EvidenceFamily, ...]
    reasons: tuple[str, ...]
    lane: OpportunityLane | None = None
    direction: TradeDirection | None = None
    holding_horizon: HoldingHorizon | None = None
    runner_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("strategy eligibility evaluation requires reasons")
        if len(set(self.present_evidence)) != len(self.present_evidence):
            raise ValueError("present evidence families must be unique")
        if len(set(self.missing_mandatory_evidence)) != len(self.missing_mandatory_evidence):
            raise ValueError("missing evidence families must be unique")


def evaluate_strategy_eligibility(
    strategy: StrategyType,
    *,
    market_state: PrimaryMarketState | None,
    evidence: tuple[EvidenceObservation, ...] = (),
    lane: OpportunityLane | None = None,
    direction: TradeDirection | None = None,
    holding_horizon: HoldingHorizon | None = None,
) -> StrategyEligibilityEvaluation:
    """Evaluate one strategy without changing live routing or candidate approval."""

    declaration = strategy_eligibility(strategy)
    present = tuple(dict.fromkeys(item.family for item in evidence))
    missing = tuple(family for family in declaration.mandatory_evidence if family not in present)

    if market_state is None:
        return StrategyEligibilityEvaluation(
            strategy=strategy,
            state=StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA,
            market_state=None,
            present_evidence=present,
            missing_mandatory_evidence=missing,
            reasons=("canonical market state is unavailable",),
        )
    if market_state in declaration.prohibited_states:
        return StrategyEligibilityEvaluation(
            strategy=strategy,
            state=StrategyEligibilityState.PROHIBITED_STATE,
            market_state=market_state,
            present_evidence=present,
            missing_mandatory_evidence=missing,
            reasons=(f"{strategy.value} prohibits market state {market_state.value}",),
        )
    if market_state not in declaration.compatible_states:
        scalp_context = (
            lane is not None
            and lane.is_scalp
            and holding_horizon
            in {
                HoldingHorizon.SCALP,
                HoldingHorizon.SHORT,
            }
        )
        if scalp_context:
            assert lane is not None
            return StrategyEligibilityEvaluation(
                strategy=strategy,
                state=StrategyEligibilityState.COMPATIBLE_WITH_CONSTRAINTS,
                market_state=market_state,
                present_evidence=present,
                missing_mandatory_evidence=missing,
                reasons=(
                    f"{strategy.value} is allowed in {lane.value} despite broader "
                    f"{market_state.value} context; higher-timeframe opposition is "
                    "a warning and target ceiling, not a scalp veto",
                ),
                lane=lane,
                direction=direction,
                holding_horizon=holding_horizon,
                runner_allowed=False,
            )
        return StrategyEligibilityEvaluation(
            strategy=strategy,
            state=StrategyEligibilityState.INCOMPATIBLE_STATE,
            market_state=market_state,
            present_evidence=present,
            missing_mandatory_evidence=missing,
            reasons=(f"{strategy.value} is not declared for market state {market_state.value}",),
            lane=lane,
            direction=direction,
            holding_horizon=holding_horizon,
        )
    if missing:
        return StrategyEligibilityEvaluation(
            strategy=strategy,
            state=StrategyEligibilityState.INSUFFICIENT_EVIDENCE_METADATA,
            market_state=market_state,
            present_evidence=present,
            missing_mandatory_evidence=missing,
            reasons=(
                "canonical evidence metadata is missing mandatory families: "
                + ", ".join(item.value for item in missing),
            ),
        )
    return StrategyEligibilityEvaluation(
        strategy=strategy,
        state=StrategyEligibilityState.COMPATIBLE,
        market_state=market_state,
        present_evidence=present,
        missing_mandatory_evidence=(),
        reasons=(
            f"{strategy.value} is compatible with {market_state.value} and has "
            "all mandatory evidence families",
        ),
    )


def evaluate_strategy_registry(
    *,
    market_state: PrimaryMarketState | None,
    evidence: tuple[EvidenceObservation, ...] = (),
) -> tuple[StrategyEligibilityEvaluation, ...]:
    return tuple(
        evaluate_strategy_eligibility(
            strategy,
            market_state=market_state,
            evidence=evidence,
        )
        for strategy in StrategyType
    )


def strategy_eligibility_evaluation_payload(
    evaluation: StrategyEligibilityEvaluation,
) -> dict[str, Any]:
    return {
        "strategy": evaluation.strategy.value,
        "state": evaluation.state.value,
        "market_state": (
            None if evaluation.market_state is None else evaluation.market_state.value
        ),
        "present_evidence": [item.value for item in evaluation.present_evidence],
        "missing_mandatory_evidence": [
            item.value for item in evaluation.missing_mandatory_evidence
        ],
        "reasons": list(evaluation.reasons),
        "lane": None if evaluation.lane is None else evaluation.lane.value,
        "direction": None if evaluation.direction is None else evaluation.direction.value,
        "holding_horizon": None
        if evaluation.holding_horizon is None
        else evaluation.holding_horizon.value,
        "runner_allowed": evaluation.runner_allowed,
    }


__all__ = [
    "StrategyEligibilityEvaluation",
    "StrategyEligibilityState",
    "evaluate_strategy_eligibility",
    "evaluate_strategy_registry",
    "strategy_eligibility_evaluation_payload",
]
