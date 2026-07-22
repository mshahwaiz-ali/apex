import pytest

from apex.strategies import (
    EntryMode,
    EntryOpportunityHorizon,
    EntryReference,
    EntrySelectionConfig,
    TradeDirection,
    select_entry_zone,
)
from apex.strategies.entry import find_entry_zones


def test_cmp_preferred_when_waiting_improves_too_little() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=96.0,
        target_price=108.0,
        references=(
            EntryReference(
                price=99.8,
                mode=EntryMode.PULLBACK,
                rationale=("minor pullback",),
            ),
        ),
    )

    assert zone.preferred == 100.0
    assert zone.mode is EntryMode.MARKET_NEAR
    assert zone.max_chase_price == pytest.approx(101.6)
    assert zone.expires_after_seconds == 900


def test_pullback_ranks_first_but_cmp_path_remains_available() -> None:
    zones = find_entry_zones(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=98.0,
        target_price=106.0,
        references=(
            EntryReference(
                price=99.0,
                mode=EntryMode.PULLBACK,
                rationale=("nearby support retest",),
            ),
        ),
    )

    assert zones[0].preferred == 99.0
    assert zones[0].mode is EntryMode.PULLBACK
    assert zones[1].preferred == 100.0
    assert zones[1].mode is EntryMode.MARKET_NEAR


def test_distant_structurally_valid_entry_is_preserved_as_future_trigger() -> None:
    zones = find_entry_zones(
        current_price=100.0,
        atr=1.0,
        direction=TradeDirection.LONG,
        invalidation_price=95.0,
        target_price=110.0,
        references=(
            EntryReference(
                price=95.5,
                mode=EntryMode.PULLBACK,
                rationale=("future structural pullback",),
            ),
        ),
    )

    assert {zone.preferred for zone in zones} == {95.5, 100.0}
    future = next(zone for zone in zones if zone.preferred == 95.5)
    assert future.horizon is EntryOpportunityHorizon.FUTURE_TRIGGER


def test_atr_distance_can_allow_entry_beyond_percentage_limit() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=10.0,
        direction=TradeDirection.LONG,
        invalidation_price=90.0,
        target_price=120.0,
        references=(
            EntryReference(
                price=96.0,
                mode=EntryMode.PULLBACK,
                rationale=("ATR-valid pullback",),
            ),
        ),
        config=EntrySelectionConfig(
            max_percentage_distance=0.01,
            max_atr_distance=0.5,
            minimum_risk_reward_improvement=0.0,
        ),
        allow_market_entry=False,
    )

    assert zone.preferred == 96.0
    assert zone.atr_distance == 0.4


def test_percentage_distance_can_allow_entry_beyond_atr_limit() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=0.5,
        direction=TradeDirection.LONG,
        invalidation_price=98.0,
        target_price=106.0,
        references=(
            EntryReference(
                price=99.0,
                mode=EntryMode.PULLBACK,
                rationale=("percentage-valid pullback",),
            ),
        ),
        config=EntrySelectionConfig(
            max_percentage_distance=0.02,
            max_atr_distance=0.5,
            minimum_risk_reward_improvement=0.0,
        ),
        allow_market_entry=False,
    )

    assert zone.preferred == 99.0
    assert zone.distance_from_current == 0.01


def test_scaled_reference_builds_scaled_entry_zone() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=97.0,
        target_price=108.0,
        references=(
            EntryReference(
                price=99.0,
                mode=EntryMode.RETEST,
                rationale=("scaled retest",),
                scaled=True,
            ),
        ),
        config=EntrySelectionConfig(minimum_risk_reward_improvement=0.0),
        allow_market_entry=False,
    )

    assert zone.mode is EntryMode.SCALED_ENTRY
    assert zone.lower < zone.preferred < zone.upper


def test_short_geometry_is_symmetric() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.SHORT,
        invalidation_price=102.0,
        target_price=94.0,
        references=(
            EntryReference(
                price=101.0,
                mode=EntryMode.PULLBACK,
                rationale=("nearby resistance retest",),
            ),
        ),
        allow_market_entry=False,
    )

    assert zone.preferred == 101.0
    assert zone.max_chase_price == pytest.approx(99.4)


def test_explicit_reference_geometry_remains_authoritative() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=96.0,
        target_price=110.0,
        references=(
            EntryReference(
                price=98.5,
                mode=EntryMode.RETEST,
                rationale=("generator-defined breakout retest",),
                zone_lower=98.2,
                zone_upper=98.8,
                trigger_price=99.1,
                max_chase_price=99.4,
                expires_after_seconds=2_700,
            ),
        ),
        config=EntrySelectionConfig(minimum_risk_reward_improvement=0.0),
        allow_market_entry=False,
    )

    assert zone.lower == 98.2
    assert zone.preferred == 98.5
    assert zone.upper == 98.8
    assert zone.max_chase_price == 99.4
    assert zone.expires_after_seconds == 2_700


def test_explicit_short_maximum_chase_is_preserved() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.SHORT,
        invalidation_price=104.0,
        target_price=92.0,
        references=(
            EntryReference(
                price=101.0,
                mode=EntryMode.RETEST,
                rationale=("generator-defined resistance retest",),
                zone_lower=100.8,
                zone_upper=101.2,
                max_chase_price=99.7,
            ),
        ),
        config=EntrySelectionConfig(minimum_risk_reward_improvement=0.0),
        allow_market_entry=False,
    )

    assert zone.lower == 100.8
    assert zone.upper == 101.2
    assert zone.max_chase_price == 99.7


def test_entry_reference_rejects_partial_or_invalid_explicit_zone() -> None:
    with pytest.raises(ValueError, match="provided together"):
        EntryReference(
            price=99.0,
            mode=EntryMode.RETEST,
            rationale=("partial zone",),
            zone_lower=98.5,
        )

    with pytest.raises(ValueError, match="inside explicit zone"):
        EntryReference(
            price=99.0,
            mode=EntryMode.RETEST,
            rationale=("invalid preferred",),
            zone_lower=99.2,
            zone_upper=99.8,
        )


def test_market_entry_uses_tick_atr_and_spread_aware_micro_band() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=98.0,
        target_price=106.0,
        tick_size=0.05,
        spread_percentage=0.20,
    )

    assert zone.lower == pytest.approx(99.9)
    assert zone.upper == pytest.approx(100.1)


@pytest.mark.parametrize(
    ("direction", "max_chase", "expected"),
    [
        (TradeDirection.LONG, 98.7, 99.2),
        (TradeDirection.SHORT, 101.3, 100.8),
    ],
)
def test_clamps_directionally_malformed_maximum_chase_to_zone_edge(
    direction: TradeDirection,
    max_chase: float,
    expected: float,
) -> None:
    bullish = direction is TradeDirection.LONG
    zone = select_entry_zone(
        current_price=100.0,
        atr=2.0,
        direction=direction,
        invalidation_price=96.0 if bullish else 104.0,
        target_price=108.0 if bullish else 92.0,
        references=(
            EntryReference(
                price=99.0 if bullish else 101.0,
                mode=EntryMode.RETEST,
                rationale=("malformed chase",),
                zone_lower=98.8 if bullish else 100.8,
                zone_upper=99.2 if bullish else 101.2,
                max_chase_price=max_chase,
            ),
        ),
        config=EntrySelectionConfig(minimum_risk_reward_improvement=0.0),
        allow_market_entry=False,
    )

    assert zone.max_chase_price == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_rejects_non_finite_market_geometry(value: float) -> None:
    with pytest.raises(ValueError):
        select_entry_zone(
            current_price=value,
            atr=2.0,
            direction=TradeDirection.LONG,
            invalidation_price=98.0,
            target_price=106.0,
        )


def test_rejects_invalid_directional_geometry() -> None:
    with pytest.raises(ValueError, match="long geometry"):
        select_entry_zone(
            current_price=100.0,
            atr=2.0,
            direction=TradeDirection.LONG,
            invalidation_price=101.0,
            target_price=106.0,
        )


def test_low_rr_improvement_reference_is_preserved_but_cmp_can_rank_first() -> None:
    zones = find_entry_zones(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=96.0,
        target_price=108.0,
        references=(
            EntryReference(
                price=99.8,
                mode=EntryMode.PULLBACK,
                rationale=("minor future pullback",),
            ),
        ),
    )

    assert zones[0].preferred == 100.0
    assert any(zone.preferred == 99.8 for zone in zones)
    preserved = next(zone for zone in zones if zone.preferred == 99.8)
    assert any("preserved as a future setup" in reason for reason in preserved.rationale)
