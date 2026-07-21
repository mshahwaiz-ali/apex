"""Regression tests for retaining multiple valid entry opportunities."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.strategies.contracts import (
    EntryMode,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import EntryReference, EntrySelectionConfig, find_entry_zones
from apex.strategies.orchestration import _expand_candidate_entry_paths
from apex.strategies.strategy_types import StrategyType


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
    assert zones[1].mode is EntryMode.MARKET_NEAR


def test_cmp_and_pullback_are_expanded_into_independent_candidate_paths() -> None:
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
    )
    candidate = TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 22, tzinfo=UTC),
        entry=zones[0],
        entry_opportunities=zones,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=95.0,
            rationale=("support failure",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=112.0,
                    label="TP1",
                    rationale=("prior high",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("trend remains intact",)),
        metadata={
            "entry_confirmation_complete": True,
            "retest_trigger_level": 98.5,
        },
    )

    paths = _expand_candidate_entry_paths(candidate)

    assert tuple(path.entry.mode for path in paths) == (
        EntryMode.MARKET_NEAR,
        EntryMode.PULLBACK,
    )
    assert paths[0].metadata["entry_sequence_role"] == "current_cmp"
    assert "retest_trigger_level" not in paths[0].metadata
    assert paths[1].metadata["entry_sequence_role"] == "strategy_primary"


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
