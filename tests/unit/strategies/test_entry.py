import pytest

from apex.strategies import (
    EntryMode,
    EntryReference,
    EntrySelectionConfig,
    TradeDirection,
    select_entry_zone,
)


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


def test_nearby_pullback_preferred_when_risk_reward_materially_improves() -> None:
    zone = select_entry_zone(
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

    assert zone.preferred == 99.0
    assert zone.mode is EntryMode.PULLBACK


def test_distant_entry_is_rejected() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=1.0,
        direction=TradeDirection.LONG,
        invalidation_price=95.0,
        target_price=110.0,
        references=(
            EntryReference(
                price=95.5,
                mode=EntryMode.PULLBACK,
                rationale=("too distant",),
            ),
        ),
    )

    assert zone.preferred == 100.0


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
    )

    assert zone.preferred == 101.0


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
