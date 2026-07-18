"""Regression tests for retaining multiple valid entry opportunities."""

from __future__ import annotations

from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry import EntryReference, EntrySelectionConfig, find_entry_zones


def test_market_and_pullback_entries_are_both_preserved() -> None:
    zones = find_entry_zones(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=95.0,
        target_price=112.0,
        references=(
            EntryReference(
                price=98.5,
                mode=EntryMode.PULLBACK,
                rationale=("fast EMA pullback",),
            ),
        ),
        config=EntrySelectionConfig(
            max_percentage_distance=0.03,
            max_atr_distance=1.0,
            minimum_risk_reward_improvement=0.05,
        ),
        allow_market_entry=True,
    )

    assert len(zones) == 2
    assert {zone.mode for zone in zones} == {EntryMode.MARKET_NEAR, EntryMode.PULLBACK}
    assert zones[0].mode is EntryMode.PULLBACK


def test_duplicate_entry_references_are_deduplicated() -> None:
    reference = EntryReference(
        price=98.5,
        mode=EntryMode.RETEST,
        rationale=("breakout retest",),
    )
    zones = find_entry_zones(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=95.0,
        target_price=112.0,
        references=(reference, reference),
        config=EntrySelectionConfig(
            max_percentage_distance=0.03,
            max_atr_distance=1.0,
            minimum_risk_reward_improvement=0.05,
        ),
        allow_market_entry=False,
    )

    assert len(zones) == 1
    assert zones[0].mode is EntryMode.RETEST


def test_unqualified_reference_does_not_hide_valid_market_entry() -> None:
    zones = find_entry_zones(
        current_price=100.0,
        atr=2.0,
        direction=TradeDirection.LONG,
        invalidation_price=95.0,
        target_price=112.0,
        references=(
            EntryReference(
                price=99.9,
                mode=EntryMode.PULLBACK,
                rationale=("negligible improvement",),
            ),
        ),
        config=EntrySelectionConfig(
            max_percentage_distance=0.03,
            max_atr_distance=1.0,
            minimum_risk_reward_improvement=0.20,
        ),
        allow_market_entry=True,
    )

    assert len(zones) == 1
    assert zones[0].mode is EntryMode.MARKET_NEAR
