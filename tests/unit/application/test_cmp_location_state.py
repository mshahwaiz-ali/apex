from __future__ import annotations

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
    CmpLocationState,
    CmpZonePosition,
    build_cmp_distance_diagnostics,
    classify_cmp_location_state,
    opportunity_portfolio_payload,
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
    cmp: float,
    lower: float = 99.0,
    upper: float = 101.0,
    preferred: float = 100.0,
    maximum_chase: float,
    executable: bool = False,
) -> DiscoverySetup:
    stop_price = 97.0 if direction is TradeDirection.LONG else 103.0
    target_price = 106.0 if direction is TradeDirection.LONG else 94.0
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=direction,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(
            lower,
            upper,
            preferred,
            cmp,
            maximum_chase,
            lower <= cmp <= upper,
        ),
        stop_loss=StopLoss(stop_price, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", target_price, 6.0, 2.0, ("liquidity",)),),
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


def test_location_classifier_preserves_raw_zone_state_without_chase_breach() -> None:
    assert (
        classify_cmp_location_state(
            zone_position=CmpZonePosition.BELOW_ENTRY_ZONE,
            beyond_maximum_chase=False,
        )
        is CmpLocationState.BELOW_ENTRY_ZONE
    )
    assert (
        classify_cmp_location_state(
            zone_position=CmpZonePosition.INSIDE_ENTRY_ZONE,
            beyond_maximum_chase=False,
        )
        is CmpLocationState.INSIDE_ENTRY_ZONE
    )
    assert (
        classify_cmp_location_state(
            zone_position=CmpZonePosition.ABOVE_ENTRY_ZONE,
            beyond_maximum_chase=False,
        )
        is CmpLocationState.ABOVE_ENTRY_ZONE
    )


def test_beyond_chase_has_precedence_for_long_and_short() -> None:
    long_setup = _setup(
        "long-beyond",
        TradeDirection.LONG,
        cmp=103.0,
        maximum_chase=102.0,
    )
    short_setup = _setup(
        "short-beyond",
        TradeDirection.SHORT,
        cmp=97.0,
        maximum_chase=98.0,
    )

    assert (
        build_cmp_distance_diagnostics(long_setup).location_state
        is CmpLocationState.BEYOND_MAXIMUM_CHASE
    )
    assert (
        build_cmp_distance_diagnostics(short_setup).location_state
        is CmpLocationState.BEYOND_MAXIMUM_CHASE
    )


def test_wrong_side_of_zone_is_not_implicitly_a_chase_breach() -> None:
    long_below = _setup(
        "long-below",
        TradeDirection.LONG,
        cmp=98.0,
        maximum_chase=102.0,
    )
    short_above = _setup(
        "short-above",
        TradeDirection.SHORT,
        cmp=102.0,
        maximum_chase=98.0,
    )

    assert (
        build_cmp_distance_diagnostics(long_below).location_state
        is CmpLocationState.BELOW_ENTRY_ZONE
    )
    assert (
        build_cmp_distance_diagnostics(short_above).location_state
        is CmpLocationState.ABOVE_ENTRY_ZONE
    )


def test_location_state_is_additive_and_does_not_change_slot_assignment() -> None:
    current = _setup(
        "current",
        TradeDirection.LONG,
        cmp=103.0,
        maximum_chase=102.0,
        executable=True,
    )
    nearby = _setup(
        "nearby",
        TradeDirection.SHORT,
        cmp=102.0,
        maximum_chase=98.0,
        executable=False,
    )

    portfolio = portfolio_from_setups(
        (current, nearby),
        symbol="BTCUSDT",
        cmp=103.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    payload = opportunity_portfolio_payload(portfolio)

    assert portfolio.current_long is not None
    assert portfolio.current_long.opportunity_id == "current"
    assert portfolio.nearby_short is not None
    assert portfolio.nearby_short.opportunity_id == "nearby"
    assert payload["current_long"]["cmp_distance"]["location_state"] == ("beyond_maximum_chase")
    assert payload["nearby_short"]["cmp_distance"]["location_state"] == ("above_entry_zone")


def test_scan_and_analyze_serialize_identical_location_truth() -> None:
    setup = _setup(
        "same",
        TradeDirection.LONG,
        cmp=98.0,
        maximum_chase=102.0,
    )
    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)
    analyze_payload = opportunity_portfolio_payload(analyze)

    assert (
        scan_payload["nearby_long"]["cmp_distance"]
        == analyze_payload["nearby_long"]["cmp_distance"]
    )
