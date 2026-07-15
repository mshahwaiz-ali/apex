"""Canonical research-only spot strategy and planning orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.spot_planning import SpotPlanningRequest, SpotPlanningResult, build_spot_plan
from apex.application.spot_strategies import evaluate_spot_strategies
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy import (
    SpotStrategyDecision,
    SpotStrategyInput,
    SpotStrategyRoutingResult,
)

SPOT_ANALYSIS_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SpotAnalysisRequest:
    strategy_input: SpotStrategyInput
    account: SpotAccountInput
    support_price: float
    resistance_price: float
    deeper_support_price: float
    recovery_entry_price: float
    correlated_sector_exposure: float = 0.0


@dataclass(frozen=True, slots=True)
class SpotAnalysisResult:
    routing: SpotStrategyRoutingResult
    planning: SpotPlanningResult | None


def analyze_spot_request(
    request: SpotAnalysisRequest,
    *,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig | None = None,
) -> SpotAnalysisResult:
    """Evaluate all spot strategies and build a plan only for an approved selection."""

    routing = evaluate_spot_strategies(request.strategy_input, config=strategy_config)
    selected = routing.selected
    if selected is None or selected.decision is not SpotStrategyDecision.APPROVE:
        return SpotAnalysisResult(routing=routing, planning=None)

    minimum_planned_entry = min(
        request.strategy_input.current_price,
        request.support_price,
        request.deeper_support_price,
        request.recovery_entry_price,
    )
    if selected.invalidation_price >= minimum_planned_entry:
        rejected = selected.model_copy(
            update={
                "decision": SpotStrategyDecision.REJECT,
                "rejection_reasons": (
                    *selected.rejection_reasons,
                    "strategy invalidation is not below all planned spot entries",
                ),
            }
        )
        candidates = tuple(
            rejected if candidate is selected else candidate
            for candidate in routing.candidates
        )
        return SpotAnalysisResult(
            routing=routing.model_copy(
                update={
                    "selected": None,
                    "candidates": candidates,
                }
            ),
            planning=None,
        )

    planning = build_spot_plan(
        SpotPlanningRequest(
            candidate=selected,
            account=request.account,
            current_price=request.strategy_input.current_price,
            support_price=request.support_price,
            resistance_price=request.resistance_price,
            deeper_support_price=request.deeper_support_price,
            recovery_entry_price=request.recovery_entry_price,
            correlated_sector_exposure=request.correlated_sector_exposure,
        ),
        config=product_config,
    )
    return SpotAnalysisResult(routing=routing, planning=planning)


def spot_analysis_result_to_payload(result: SpotAnalysisResult) -> dict[str, Any]:
    """Serialize one canonical spot analysis without futures-only fields."""

    planning_payload: dict[str, Any] | None = None
    if result.planning is not None:
        planning_payload = {
            "entry_plan": result.planning.entry_plan.model_dump(mode="json"),
            "stop_plan": result.planning.stop_plan.model_dump(mode="json"),
            "position_plan": result.planning.position_plan.model_dump(mode="json"),
            "target_plan": result.planning.target_plan.model_dump(mode="json"),
            "lifecycle": result.planning.lifecycle.model_dump(mode="json"),
        }

    return {
        "schema_version": SPOT_ANALYSIS_SCHEMA_VERSION,
        "selected_strategy": (
            result.routing.selected.model_dump(mode="json")
            if result.routing.selected is not None
            else None
        ),
        "candidates": [candidate.model_dump(mode="json") for candidate in result.routing.candidates],
        "planning": planning_payload,
        "warnings": [
            "spot analysis is research and paper-trading guidance only",
            "historical and forward-paper validation remain required",
        ],
    }
