from __future__ import annotations

from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.opportunity_portfolio import AnalysisMode, portfolio_from_setups


def _setup():
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    return assessment.setup


def test_live_portfolio_retains_higher_score_duplicate_geometry() -> None:
    setup = _setup()
    weaker = replace(setup, candidate_id="weaker", confidence_score=60.0)
    stronger = replace(setup, candidate_id="stronger", confidence_score=90.0)

    portfolio = portfolio_from_setups(
        (weaker, stronger),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert tuple(opportunity.opportunity_id for opportunity in portfolio.opportunities) == (
        "stronger",
    )


def test_live_portfolio_selection_is_input_order_independent() -> None:
    setup = _setup()
    first = replace(setup, candidate_id="a", confidence_score=75.0)
    second = replace(setup, candidate_id="b", confidence_score=85.0)

    forward = portfolio_from_setups(
        (first, second),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    reverse = portfolio_from_setups(
        (second, first),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    assert tuple(opportunity.opportunity_id for opportunity in forward.opportunities) == tuple(
        opportunity.opportunity_id for opportunity in reverse.opportunities
    )
    assert forward.primary_opportunity is not None
    assert forward.primary_opportunity.opportunity_id == "b"


def test_live_portfolio_allows_distinct_current_and_nearby_lanes() -> None:
    setup = _setup()
    current = replace(
        setup,
        candidate_id="current",
        confidence_score=90.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    nearby = replace(
        setup,
        candidate_id="nearby",
        confidence_score=80.0,
        execution_allowed_now=False,
        entry=replace(
            setup.entry,
            lower=setup.entry.lower * 1.02,
            preferred=setup.entry.preferred * 1.02,
            upper=setup.entry.upper * 1.02,
            maximum_chase_price=setup.entry.maximum_chase_price * 1.02,
            current_price_inside_zone=False,
        ),
    )

    portfolio = portfolio_from_setups(
        (nearby, current),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby"


def test_live_portfolio_keeps_best_candidate_per_lane() -> None:
    setup = _setup()
    best = replace(setup, candidate_id="best", confidence_score=88.0)
    second = replace(
        setup,
        candidate_id="second",
        confidence_score=80.0,
        take_profits=tuple(
            replace(target, price=target.price * 1.001) for target in setup.take_profits
        ),
    )

    portfolio = portfolio_from_setups(
        (second, best),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert tuple(opportunity.opportunity_id for opportunity in portfolio.opportunities) == ("best",)
