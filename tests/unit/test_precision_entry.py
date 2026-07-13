"""Tests for precision-entry plan construction."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apex.application import build_precision_entry_plan
from apex.domain import PrecisionEntryScore, weighted_precision_score
from apex.strategies import TimeframeContext, TimeframeRole


def _setup(*, current_price: float = 100.5, inside_zone: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        decision_time=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
        direction=SimpleNamespace(value="long"),
        entry=SimpleNamespace(
            lower=100.0,
            upper=101.0,
            preferred=100.5,
            current_price=current_price,
            maximum_chase_price=102.0,
            current_price_inside_zone=inside_zone,
        ),
        stop_loss=SimpleNamespace(
            price=98.0,
            quality_score=0.8,
            rationale=("structure invalidation",),
        ),
        confidence_score=85.0,
    )


def test_precision_entry_plan_exposes_actionable_geometry() -> None:
    plan = build_precision_entry_plan(_setup())

    assert plan.entry_state == "READY_NOW"
    assert plan.expected_time_to_entry == "now"
    assert plan.current_distance_from_ideal == 0
    assert plan.reclaim_trigger == 101.0
    assert plan.retest_trigger == 100.5
    assert plan.fast_failure_trigger == 100.0
    assert plan.trigger_state == "UNAVAILABLE"
    assert plan.score.final_score > 0
    assert plan.missing_data_warnings


def test_precision_entry_plan_uses_low_timeframe_trigger_context() -> None:
    plan = build_precision_entry_plan(
        _setup(current_price=101.0),
        timeframe_contexts=(
            _frame("5m", TimeframeRole.ENTRY, price=101.2, rsi_slope=1.0, momentum=0.4),
            _frame("3m", TimeframeRole.REFINEMENT, price=101.1, rsi_slope=0.5, momentum=0.2),
        ),
    )

    assert plan.trigger_state == "RECLAIM_CONFIRMED"
    assert plan.trigger_timeframes == ("5m", "3m")
    assert any("reclaim confirmed" in item for item in plan.trigger_evidence)


def test_precision_entry_plan_scores_available_spread_data() -> None:
    tight = build_precision_entry_plan(
        _setup(),
        timeframe_contexts=(
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                price=100.5,
                rsi_slope=0.1,
                momentum=0.1,
                spread_percentage=0.02,
            ),
        ),
    )
    wide = build_precision_entry_plan(
        _setup(),
        timeframe_contexts=(
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                price=100.5,
                rsi_slope=0.1,
                momentum=0.1,
                spread_percentage=0.2,
            ),
        ),
    )

    assert tight.score.spread_slippage_penalty == 2.0
    assert wide.score.spread_slippage_penalty == 18.0
    assert any("acceptable" in item for item in tight.missing_data_warnings)
    assert any("too wide" in item for item in wide.missing_data_warnings)


def test_precision_entry_plan_uses_microstructure_evidence() -> None:
    supportive = build_precision_entry_plan(
        _setup(),
        timeframe_contexts=(
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                price=100.5,
                rsi_slope=0.1,
                momentum=0.1,
                order_book_depth_imbalance=0.4,
                exchange_tick_size=0.01,
                exchange_step_size=0.001,
                exchange_min_notional=5.0,
            ),
        ),
    )
    opposing = build_precision_entry_plan(
        _setup(),
        timeframe_contexts=(
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                price=100.5,
                rsi_slope=0.1,
                momentum=0.1,
                order_book_depth_imbalance=-0.4,
                exchange_tick_size=0.01,
                exchange_step_size=0.001,
                exchange_min_notional=5.0,
            ),
        ),
    )

    assert supportive.score.liquidity_quality == 88.0
    assert supportive.score.trap_penalty == 0.0
    assert opposing.score.liquidity_quality == 45.0
    assert opposing.score.trap_penalty == 20.0
    assert any("order-book depth supports" in item for item in supportive.missing_data_warnings)
    assert any("exchange precision" in item for item in supportive.missing_data_warnings)


def test_precision_entry_plan_scores_liquidation_cluster_evidence() -> None:
    adverse = build_precision_entry_plan(
        _setup(),
        timeframe_contexts=(
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                price=100.5,
                rsi_slope=0.1,
                momentum=0.1,
                order_book_depth_imbalance=0.4,
                nearest_long_cluster_distance_pct=0.25,
                nearest_short_cluster_distance_pct=1.0,
            ),
        ),
    )

    assert adverse.score.liquidity_quality == 82.0
    assert adverse.score.trap_penalty == 18.0
    assert any("adverse liquidation cluster" in item for item in adverse.missing_data_warnings)
    assert any("favorable liquidation cluster" in item for item in adverse.missing_data_warnings)


def test_precision_entry_plan_uses_canonical_entry_classifier() -> None:
    plan = build_precision_entry_plan(_setup(current_price=102.1, inside_zone=False))

    assert plan.entry_state == "MISSED_ENTRY"
    assert plan.expected_time_to_entry == "not_actionable"


def test_precision_score_rejects_incorrect_final_value() -> None:
    with pytest.raises(ValueError, match="precision final score"):
        PrecisionEntryScore(
            structural_quality=80,
            liquidity_quality=75,
            momentum_alignment=85,
            volatility_suitability=80,
            distance_from_ideal=90,
            extension_penalty=10,
            trap_penalty=0,
            spread_slippage_penalty=10,
            multi_timeframe_agreement=85,
            final_score=1,
        )


def test_weighted_precision_score_is_deterministic() -> None:
    first = weighted_precision_score(
        structural_quality=80,
        liquidity_quality=75,
        momentum_alignment=85,
        volatility_suitability=80,
        distance_from_ideal=90,
        extension_penalty=10,
        trap_penalty=0,
        spread_slippage_penalty=10,
        multi_timeframe_agreement=85,
    )
    second = weighted_precision_score(
        structural_quality=80,
        liquidity_quality=75,
        momentum_alignment=85,
        volatility_suitability=80,
        distance_from_ideal=90,
        extension_penalty=10,
        trap_penalty=0,
        spread_slippage_penalty=10,
        multi_timeframe_agreement=85,
    )

    assert first == second


def _frame(
    timeframe: str,
    role: TimeframeRole,
    *,
    price: float,
    rsi_slope: float,
    momentum: float,
    spread_percentage: float | None = None,
    order_book_depth_imbalance: float | None = None,
    exchange_tick_size: float | None = None,
    exchange_step_size: float | None = None,
    exchange_min_notional: float | None = None,
    nearest_long_cluster_distance_pct: float | None = None,
    nearest_short_cluster_distance_pct: float | None = None,
) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=price,
        spread_percentage=spread_percentage,
        order_book_depth_imbalance=order_book_depth_imbalance,
        exchange_tick_size=exchange_tick_size,
        exchange_step_size=exchange_step_size,
        exchange_min_notional=exchange_min_notional,
        nearest_long_cluster_distance_pct=nearest_long_cluster_distance_pct,
        nearest_short_cluster_distance_pct=nearest_short_cluster_distance_pct,
        features=SimpleNamespace(rsi_slope=rsi_slope, rate_of_change=momentum),
        structure=object(),
        liquidity=object(),
    )
