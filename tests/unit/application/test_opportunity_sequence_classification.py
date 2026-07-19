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
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    SequenceRole,
    classify_setup_sequence_role,
    portfolio_from_setups,
)
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
) -> DiscoverySetup:
    if direction is TradeDirection.LONG:
        entry = ActionableEntry(99.0, 101.0, 100.0, 100.0, 102.0, True)
        stop = StopLoss(97.0, 3.0, 3.0, ("structure",))
        target = TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",))
    else:
        entry = ActionableEntry(99.0, 101.0, 100.0, 100.0, 98.0, True)
        stop = StopLoss(103.0, 3.0, 3.0, ("structure",))
        target = TakeProfit("TP1", 94.0, 6.0, 2.0, ("liquidity",))
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=score,
        entry=entry,
        stop_loss=stop,
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


def test_classifier_uses_canonical_execution_validity_only() -> None:
    current = _setup("current", TradeDirection.LONG, executable=True)
    nearby = _setup("nearby", TradeDirection.LONG, executable=False)

    assert classify_setup_sequence_role(current) is SequenceRole.CURRENT
    assert classify_setup_sequence_role(nearby) is SequenceRole.NEARBY


def test_classifier_does_not_use_score_to_promote_nearby_setup() -> None:
    current = _setup("current", TradeDirection.LONG, executable=True, score=40.0)
    nearby = _setup("nearby", TradeDirection.LONG, executable=False, score=99.0)

    assert classify_setup_sequence_role(current) is SequenceRole.CURRENT
    assert classify_setup_sequence_role(nearby) is SequenceRole.NEARBY


def test_classifier_is_direction_symmetric() -> None:
    assert (
        classify_setup_sequence_role(_setup("long-current", TradeDirection.LONG, executable=True))
        is SequenceRole.CURRENT
    )
    assert (
        classify_setup_sequence_role(_setup("short-current", TradeDirection.SHORT, executable=True))
        is SequenceRole.CURRENT
    )
    assert (
        classify_setup_sequence_role(_setup("long-nearby", TradeDirection.LONG, executable=False))
        is SequenceRole.NEARBY
    )
    assert (
        classify_setup_sequence_role(_setup("short-nearby", TradeDirection.SHORT, executable=False))
        is SequenceRole.NEARBY
    )


def test_portfolio_slotting_uses_first_class_classification() -> None:
    nearby_high_score = _setup(
        "nearby-high",
        TradeDirection.LONG,
        executable=False,
        score=99.0,
    )
    current_low_score = _setup(
        "current-low",
        TradeDirection.LONG,
        executable=True,
        score=35.0,
    )

    portfolio = portfolio_from_setups(
        (nearby_high_score, current_low_score),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current-low"
    assert portfolio.nearby_long is not None
    assert portfolio.nearby_long.opportunity_id == "nearby-high"


def test_analysis_mode_does_not_change_current_nearby_classification() -> None:
    current = _setup("current", TradeDirection.SHORT, executable=True)
    nearby = replace(
        _setup("nearby", TradeDirection.SHORT, executable=False),
        entry=ActionableEntry(101.0, 103.0, 102.0, 100.0, 99.0, False),
        stop_loss=StopLoss(105.0, 3.0, 3.0, ("higher_structure",)),
    )

    scan = portfolio_from_setups(
        (current, nearby),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (current, nearby),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert scan.current_short == analyze.current_short
    assert scan.nearby_short == analyze.nearby_short
