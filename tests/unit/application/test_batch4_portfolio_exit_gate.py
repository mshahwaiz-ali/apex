from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
    TargetRole,
)
from apex.application.opportunity_portfolio import AnalysisMode, portfolio_from_setups
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    direction: TradeDirection,
    *,
    executable: bool,
    score: float = 70.0,
    preferred: float = 100.0,
    lower: float = 99.0,
    upper: float = 101.0,
    stop_price: float | None = None,
) -> DiscoverySetup:
    if direction is TradeDirection.LONG:
        maximum_chase = upper + 1.0
        resolved_stop = lower - 2.0 if stop_price is None else stop_price
        target = TakeProfit("TP1", preferred + 6.0, 6.0, 2.0, ("liquidity",))
    else:
        maximum_chase = lower - 1.0
        resolved_stop = upper + 2.0 if stop_price is None else stop_price
        target = TakeProfit("TP1", preferred - 6.0, 6.0, 2.0, ("liquidity",))

    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=score,
        entry=ActionableEntry(
            lower,
            upper,
            preferred,
            100.0,
            maximum_chase,
            lower <= 100.0 <= upper,
        ),
        stop_loss=StopLoss(
            resolved_stop,
            abs(preferred - resolved_stop),
            abs(preferred - resolved_stop) / preferred * 100.0,
            ("structure",),
        ),
        take_profits=(target,),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=executable,
    )


def _portfolio(
    setups: tuple[DiscoverySetup, ...],
    mode: AnalysisMode = AnalysisMode.ANALYZE_FULL,
):
    return portfolio_from_setups(
        setups,
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=mode,
    )


def _ids(portfolio) -> tuple[str, ...]:
    return tuple(item.opportunity_id for item in portfolio.opportunities)


def test_valid_current_long_and_short_survive_simultaneously() -> None:
    portfolio = _portfolio(
        (
            _setup("current-long", TradeDirection.LONG, executable=True),
            _setup("current-short", TradeDirection.SHORT, executable=True),
        )
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert portfolio.current_short is not None
    assert portfolio.current_short.opportunity_id == "current-short"


def test_higher_scoring_nearby_opportunity_does_not_displace_current_slot() -> None:
    current = _setup(
        "current-long",
        TradeDirection.LONG,
        executable=True,
        score=55.0,
    )
    nearby = _setup(
        "nearby-long",
        TradeDirection.LONG,
        executable=False,
        score=99.0,
        lower=96.0,
        upper=98.0,
        preferred=97.0,
        stop_price=94.0,
    )

    portfolio = _portfolio((nearby, current))

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-long"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby-long"


def test_structurally_valid_missed_entry_remains_as_alert_only_nearby_plan() -> None:
    missed = replace(
        _setup(
            "missed-long",
            TradeDirection.LONG,
            executable=False,
            lower=96.0,
            upper=98.0,
            preferred=97.0,
            stop_price=94.0,
        ),
        entry_status=EntryStatus.MISSED_ENTRY,
        entry=ActionableEntry(96.0, 98.0, 97.0, 103.0, 99.0, False),
    )

    portfolio = _portfolio((missed,))

    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "missed-long"
    assert portfolio.nearby_long.setup.execution_allowed_now is False
    assert portfolio.nearby_long.setup.entry.lower == 96.0
    assert portfolio.nearby_long.setup.entry.maximum_chase_price == 99.0


def test_runner_qualified_setup_gets_independent_runner_lane_identity() -> None:
    source = _setup("qualified", TradeDirection.LONG, executable=True)
    runner_target = replace(
        source.take_profits[0],
        target_role=TargetRole.EXTENSION_CANDIDATE,
        runner_qualified=True,
    )
    qualified = replace(
        source,
        take_profits=(runner_target,),
        runner_qualified=True,
        runner_qualification_reason="aligned HTF continuation",
    )

    portfolio = _portfolio((qualified,))

    assert portfolio.current_long is not None
    assert portfolio.runner_plan is not None
    assert portfolio.runner_plan.opportunity_id == "qualified:runner"
    assert portfolio.runner_plan.effective_lane.value == "runner"
    assert portfolio.current_long.opportunity_id != portfolio.runner_plan.opportunity_id


def test_distinct_sequential_opportunities_remain_separate() -> None:
    primary = _setup("primary", TradeDirection.LONG, executable=True)
    second_leg = _setup(
        "second-leg",
        TradeDirection.LONG,
        executable=True,
        lower=97.0,
        upper=99.0,
        preferred=98.0,
        stop_price=95.0,
    )
    reversal = _setup(
        "reversal",
        TradeDirection.SHORT,
        executable=False,
        lower=104.0,
        upper=106.0,
        preferred=105.0,
        stop_price=108.0,
    )

    portfolio = _portfolio((primary, second_leg, reversal))

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "primary"
    assert portfolio.nearby_short is not None
    assert portfolio.nearby_short.opportunity_id == "reversal"
    assert tuple(item.opportunity_id for item in portfolio.follow_up_opportunities) == (
        "second-leg",
    )


def test_semantic_duplicates_merge_deterministically_to_first_ranked_candidate() -> None:
    first = _setup("first", TradeDirection.LONG, executable=True)
    duplicate = replace(first, candidate_id="duplicate", confidence_score=99.0)

    portfolio = _portfolio((first, duplicate))
    reversed_portfolio = _portfolio((duplicate, first))

    assert _ids(portfolio) == ("duplicate",)
    assert _ids(reversed_portfolio) == ("duplicate",)


def test_portfolio_order_is_deterministic_for_identical_inputs() -> None:
    setups = (
        _setup("current-long", TradeDirection.LONG, executable=True),
        _setup("current-short", TradeDirection.SHORT, executable=True),
        _setup(
            "nearby-long",
            TradeDirection.LONG,
            executable=False,
            lower=96.0,
            upper=98.0,
            preferred=97.0,
            stop_price=94.0,
        ),
        _setup(
            "nearby-short",
            TradeDirection.SHORT,
            executable=False,
            lower=102.0,
            upper=104.0,
            preferred=103.0,
            stop_price=106.0,
        ),
        _setup(
            "follow-up",
            TradeDirection.LONG,
            executable=True,
            lower=97.0,
            upper=99.0,
            preferred=98.0,
            stop_price=95.0,
        ),
    )

    first = _portfolio(setups)
    second = _portfolio(setups)

    assert first == second
    assert _ids(first) == _ids(second)


def test_scan_never_exposes_follow_ups_beyond_compact_slots() -> None:
    first = _setup("current-long", TradeDirection.LONG, executable=True)
    extra = _setup(
        "extra-current-long",
        TradeDirection.LONG,
        executable=True,
        lower=97.0,
        upper=99.0,
        preferred=98.0,
        stop_price=95.0,
    )

    portfolio = _portfolio((first, extra), AnalysisMode.SCAN_CMP_FIRST)

    assert portfolio.current_long is not None
    assert portfolio.follow_up_opportunities == ()
    assert len(portfolio.opportunities) <= 4


def test_analyze_retains_additional_valid_follow_ups() -> None:
    first = _setup("current-long", TradeDirection.LONG, executable=True)
    extra = _setup(
        "extra-current-long",
        TradeDirection.LONG,
        executable=True,
        lower=97.0,
        upper=99.0,
        preferred=98.0,
        stop_price=95.0,
    )

    portfolio = _portfolio((first, extra), AnalysisMode.ANALYZE_FULL)

    assert tuple(item.opportunity_id for item in portfolio.follow_up_opportunities) == (
        "extra-current-long",
    )


def test_empty_portfolio_is_valid_and_does_not_fabricate_trade() -> None:
    portfolio = _portfolio(())

    assert portfolio.current_long is None
    assert portfolio.current_short is None
    assert portfolio.nearby_long is None
    assert portfolio.nearby_short is None
    assert portfolio.follow_up_opportunities == ()
    assert portfolio.runner_plan is None
    assert portfolio.opportunities == ()


def test_analysis_mode_changes_breadth_only_not_fixed_slot_validity_or_setup_data() -> None:
    current = _setup("current", TradeDirection.LONG, executable=True)
    nearby = _setup(
        "nearby",
        TradeDirection.SHORT,
        executable=False,
        lower=102.0,
        upper=104.0,
        preferred=103.0,
        stop_price=106.0,
    )
    follow_up = _setup(
        "follow-up",
        TradeDirection.LONG,
        executable=True,
        lower=97.0,
        upper=99.0,
        preferred=98.0,
        stop_price=95.0,
    )
    setups = (current, nearby, follow_up)

    scan = _portfolio(setups, AnalysisMode.SCAN_CMP_FIRST)
    analyze = _portfolio(setups, AnalysisMode.ANALYZE_FULL)

    assert scan.current_long == analyze.current_long
    assert scan.current_short == analyze.current_short
    assert scan.nearby_long == analyze.nearby_long
    assert scan.nearby_short == analyze.nearby_short
    assert scan.current_long is not None
    assert scan.current_long.setup is current
    assert scan.nearby_short is not None
    assert scan.nearby_short.setup is nearby
    assert scan.follow_up_opportunities == ()
    assert tuple(item.setup for item in analyze.follow_up_opportunities) == (follow_up,)
