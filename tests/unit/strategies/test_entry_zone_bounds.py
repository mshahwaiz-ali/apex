from apex.strategies import (
    EntryMode,
    EntryReference,
    EntrySelectionConfig,
    TradeDirection,
    select_entry_zone,
)


def test_long_scaled_zone_crossing_invalidation_is_rejected() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=10.0,
        direction=TradeDirection.LONG,
        invalidation_price=98.5,
        target_price=110.0,
        references=(
            EntryReference(
                price=99.0,
                mode=EntryMode.RETEST,
                rationale=("scaled retest",),
                scaled=True,
            ),
        ),
        config=EntrySelectionConfig(
            scaled_half_width_atr=0.1,
            minimum_risk_reward_improvement=0.0,
        ),
    )

    assert zone.mode is EntryMode.MARKET_NEAR
    assert zone.preferred == 100.0


def test_short_scaled_zone_crossing_invalidation_is_rejected() -> None:
    zone = select_entry_zone(
        current_price=100.0,
        atr=10.0,
        direction=TradeDirection.SHORT,
        invalidation_price=101.5,
        target_price=90.0,
        references=(
            EntryReference(
                price=101.0,
                mode=EntryMode.RETEST,
                rationale=("scaled retest",),
                scaled=True,
            ),
        ),
        config=EntrySelectionConfig(
            scaled_half_width_atr=0.1,
            minimum_risk_reward_improvement=0.0,
        ),
    )

    assert zone.mode is EntryMode.MARKET_NEAR
    assert zone.preferred == 100.0
