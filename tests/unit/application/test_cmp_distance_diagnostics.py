from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
    SequenceRole,
    build_cmp_distance_diagnostics,
    classify_setup_sequence_role,
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
    lower: float,
    upper: float,
    preferred: float,
    maximum_chase: float,
    executable: bool,
) -> DiscoverySetup:
    stop_price = preferred - 3.0 if direction is TradeDirection.LONG else preferred + 3.0
    target_price = preferred + 6.0 if direction is TradeDirection.LONG else preferred - 6.0
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


def test_cmp_inside_zone_has_zero_zone_distance() -> None:
    setup = _setup(
        "inside",
        TradeDirection.LONG,
        cmp=100.0,
        lower=99.0,
        upper=101.0,
        preferred=99.5,
        maximum_chase=102.0,
        executable=True,
    )

    diagnostics = build_cmp_distance_diagnostics(setup)

    assert diagnostics.zone_position is CmpZonePosition.INSIDE_ENTRY_ZONE
    assert diagnostics.location_state is CmpLocationState.INSIDE_ENTRY_ZONE
    assert diagnostics.distance_to_entry_zone == 0.0
    assert diagnostics.distance_to_entry_zone_pct == 0.0
    assert diagnostics.distance_to_ideal_entry == 0.5
    assert diagnostics.distance_to_ideal_entry_pct == pytest.approx(0.5)
    assert diagnostics.beyond_maximum_chase is False


def test_cmp_below_and_above_zone_distances_use_nearest_boundary() -> None:
    below = _setup(
        "below",
        TradeDirection.LONG,
        cmp=97.0,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        maximum_chase=102.0,
        executable=False,
    )
    above = _setup(
        "above",
        TradeDirection.LONG,
        cmp=104.0,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        maximum_chase=105.0,
        executable=False,
    )

    below_diagnostics = build_cmp_distance_diagnostics(below)
    above_diagnostics = build_cmp_distance_diagnostics(above)

    assert below_diagnostics.zone_position is CmpZonePosition.BELOW_ENTRY_ZONE
    assert below_diagnostics.distance_to_entry_zone == 2.0
    assert below_diagnostics.distance_to_entry_zone_pct == pytest.approx(2.0 / 97.0 * 100.0)
    assert above_diagnostics.zone_position is CmpZonePosition.ABOVE_ENTRY_ZONE
    assert above_diagnostics.distance_to_entry_zone == 3.0
    assert above_diagnostics.distance_to_entry_zone_pct == pytest.approx(3.0 / 104.0 * 100.0)


def test_maximum_chase_breach_is_direction_aware() -> None:
    long_setup = _setup(
        "long-chased",
        TradeDirection.LONG,
        cmp=103.0,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        maximum_chase=102.0,
        executable=False,
    )
    short_setup = _setup(
        "short-chased",
        TradeDirection.SHORT,
        cmp=97.0,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        maximum_chase=98.0,
        executable=False,
    )

    assert build_cmp_distance_diagnostics(long_setup).beyond_maximum_chase is True
    assert build_cmp_distance_diagnostics(short_setup).beyond_maximum_chase is True


def test_diagnostics_do_not_change_sequence_classification() -> None:
    setup = _setup(
        "nearby-inside",
        TradeDirection.LONG,
        cmp=100.0,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        maximum_chase=102.0,
        executable=False,
    )

    diagnostics = build_cmp_distance_diagnostics(setup)

    assert diagnostics.zone_position is CmpZonePosition.INSIDE_ENTRY_ZONE
    assert classify_setup_sequence_role(setup) is SequenceRole.NEARBY


def test_serialization_exposes_additive_cmp_distance_for_both_modes() -> None:
    setup = _setup(
        "current-long",
        TradeDirection.LONG,
        cmp=100.0,
        lower=99.0,
        upper=101.0,
        preferred=99.5,
        maximum_chase=102.0,
        executable=True,
    )

    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)
    analyze_payload = opportunity_portfolio_payload(analyze)
    scan_distance = scan_payload["current_long"]["cmp_distance"]
    analyze_distance = analyze_payload["current_long"]["cmp_distance"]

    assert scan_distance == analyze_distance
    assert scan_distance == {
        "location_state": "inside_entry_zone",
        "zone_position": "inside_entry_zone",
        "distance_to_entry_zone": 0.0,
        "distance_to_entry_zone_pct": 0.0,
        "distance_to_ideal_entry": 0.5,
        "distance_to_ideal_entry_pct": 0.5,
        "distance_to_maximum_chase": 2.0,
        "distance_to_maximum_chase_pct": 2.0,
        "beyond_maximum_chase": False,
    }
