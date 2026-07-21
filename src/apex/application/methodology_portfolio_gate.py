"""Filter symbol opportunities using explicit methodology suppression decisions."""

from __future__ import annotations

from dataclasses import replace

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.application.methodology_selected_strategy_verdict import (
    SelectedStrategyVerdictState,
    derive_selected_strategy_verdict,
)
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.application.opportunity_portfolio import SymbolOpportunityPortfolio, TradeOpportunity


def filter_portfolio_by_methodology(
    portfolio: SymbolOpportunityPortfolio | None,
    decisions: tuple[StrategyEnforcementDecision, ...],
    *,
    opportunity_decisions: dict[str, StrategyEnforcementDecision] | None = None,
) -> tuple[SymbolOpportunityPortfolio | None, tuple[str, ...]]:
    """Remove only opportunities whose strategy verdict is explicitly suppressed."""

    if portfolio is None:
        return None, ()

    removed: list[str] = []

    def keep(opportunity: TradeOpportunity | None) -> TradeOpportunity | None:
        if opportunity is None:
            return None
        opportunity_decision = (
            None
            if opportunity_decisions is None
            else opportunity_decisions.get(opportunity.opportunity_id)
        )
        if opportunity_decision is not None:
            suppressed = opportunity_decision.action is StrategyEnforcementAction.SUPPRESS
        else:
            verdict = derive_selected_strategy_verdict(
                selected_strategy=opportunity.setup.strategy,
                decisions=decisions,
            )
            suppressed = verdict.state is SelectedStrategyVerdictState.SUPPRESSED
        if suppressed:
            removed.append(opportunity.opportunity_id)
            return None
        return opportunity

    filtered = replace(
        portfolio,
        current_long=keep(portfolio.current_long),
        current_short=keep(portfolio.current_short),
        nearby_long=keep(portfolio.nearby_long),
        nearby_short=keep(portfolio.nearby_short),
        follow_up_opportunities=tuple(
            item
            for item in (keep(opportunity) for opportunity in portfolio.follow_up_opportunities)
            if item is not None
        ),
        runner_plan=keep(portfolio.runner_plan),
    )
    return filtered, tuple(removed)


def assessment_from_portfolio(
    assessment: DiscoveryAssessment,
    portfolio: SymbolOpportunityPortfolio | None,
    *,
    suppression_reasons: tuple[str, ...],
) -> DiscoveryAssessment:
    """Keep the legacy compatibility assessment synchronized with the portfolio."""

    if portfolio is None:
        return assessment

    current = portfolio.current_opportunities
    nearby = portfolio.nearby_opportunities
    follow_up = portfolio.follow_up_opportunities
    executable_follow_up = next(
        (item for item in follow_up if item.setup.execution_allowed_now),
        None,
    )
    selected_opportunity = current[0] if current else executable_follow_up
    selected = None if selected_opportunity is None else selected_opportunity.setup
    developing_opportunity = next(
        (item for item in (*nearby, *follow_up) if not item.setup.execution_allowed_now),
        None,
    )
    developing = None if developing_opportunity is None else developing_opportunity.setup

    if selected is not None:
        return DiscoveryAssessment(
            symbol=assessment.symbol,
            decision_time=assessment.decision_time,
            setup=selected,
            developing_setup=developing,
        )

    reasons = (
        suppression_reasons
        or assessment.reasons
        or ("no methodology-eligible opportunity remains",)
    )
    return DiscoveryAssessment(
        symbol=assessment.symbol,
        decision_time=assessment.decision_time,
        setup=None,
        reasons=reasons,
        developing_setup=developing,
    )


__all__ = ["assessment_from_portfolio", "filter_portfolio_by_methodology"]
