"""Apply configured methodology enforcement to one completed symbol analysis."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_opportunity_context import infer_opportunity_methodology_context
from apex.application.methodology_portfolio_gate import (
    assessment_from_portfolio,
    filter_portfolio_by_methodology,
)
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_selected_strategy_verdict import (
    derive_selected_strategy_verdict,
    selected_strategy_verdict_payload,
)
from apex.application.methodology_strategy_enforcement import (
    derive_strategy_enforcement,
    derive_strategy_enforcement_registry,
)
from apex.application.methodology_strategy_evaluation import (
    evaluate_strategy_eligibility,
    evaluate_strategy_registry,
)


def apply_configured_methodology_gate(
    analysis: SymbolAnalysis,
    *,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
) -> SymbolAnalysis:
    """Apply methodology decisions to every retained portfolio opportunity."""

    normalized_mode = MethodologyGateMode(mode)
    methodology = project_analysis_methodology(analysis)
    eligibility = evaluate_strategy_registry(
        market_state=(
            None if methodology.market_state is None else methodology.market_state.primary
        ),
        evidence=methodology.evidence,
    )
    enforcement = derive_strategy_enforcement_registry(eligibility)
    selected_strategy = (
        None if analysis.assessment.setup is None else analysis.assessment.setup.strategy
    )
    selected_verdict = derive_selected_strategy_verdict(
        selected_strategy=selected_strategy,
        decisions=enforcement,
    )

    portfolio = analysis.opportunity_portfolio
    opportunity_decisions = {}
    if portfolio is not None:
        for opportunity in portfolio.opportunities:
            context = infer_opportunity_methodology_context(opportunity)
            opportunity_evaluation = evaluate_strategy_eligibility(
                opportunity.setup.strategy,
                market_state=(
                    None if methodology.market_state is None else methodology.market_state.primary
                ),
                evidence=methodology.evidence,
                lane=context.lane,
                direction=opportunity.setup.direction,
                holding_horizon=context.holding_horizon,
            )
            opportunity_decisions[opportunity.opportunity_id] = derive_strategy_enforcement(
                opportunity_evaluation
            )
    removed_ids: tuple[str, ...] = ()
    assessment = analysis.assessment
    changed = False
    reasons = ("methodology enforcement is running in shadow mode",)
    reason_codes = ("METHODOLOGY_GATE_SHADOW",)

    if normalized_mode is MethodologyGateMode.ENFORCE:
        portfolio, removed_ids = filter_portfolio_by_methodology(
            portfolio,
            enforcement,
            opportunity_decisions=opportunity_decisions,
        )
        changed = bool(removed_ids)
        reasons = (
            ("explicitly suppressed methodology opportunities were removed",)
            if changed
            else ("no portfolio opportunity was explicitly suppressed",)
        )
        reason_codes = (
            ("METHODOLOGY_PORTFOLIO_FILTERED",) if changed else ("METHODOLOGY_GATE_NO_CHANGE",)
        )
        assessment = assessment_from_portfolio(
            analysis.assessment,
            portfolio,
            suppression_reasons=reasons,
        )

    gate_payload: dict[str, Any] = {
        "mode": normalized_mode.value,
        "changed": changed,
        "reason_codes": list(reason_codes),
        "reasons": list(reasons),
        "removed_opportunity_ids": list(removed_ids),
        "opportunity_decisions": {
            opportunity_id: {
                "strategy": decision.strategy.value,
                "action": decision.action.value,
                "reason_codes": list(decision.reason_codes),
                "reasons": list(decision.reasons),
            }
            for opportunity_id, decision in opportunity_decisions.items()
        },
        "selected_strategy_verdict": selected_strategy_verdict_payload(selected_verdict),
    }
    return replace(
        analysis,
        assessment=assessment,
        opportunity_portfolio=portfolio,
        methodology=methodology,
        methodology_gate=gate_payload,
    )


__all__ = ["apply_configured_methodology_gate"]
