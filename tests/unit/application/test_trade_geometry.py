from __future__ import annotations

import pytest

from apex.application.trade_geometry import build_layered_targets, build_stop_geometry
from apex.strategies.contracts import (
    InvalidationType,
    TargetLevel,
    TargetType,
    TradeDirection,
)


def test_volatility_invalidation_does_not_receive_second_atr_buffer() -> None:
    geometry = build_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        invalidation_price=98.0,
        invalidation_type=InvalidationType.VOLATILITY,
        atr=4.0,
    )

    assert geometry.buffer == pytest.approx(0.1)
    assert geometry.price == pytest.approx(97.9)
    assert "execution buffer" in geometry.buffer_reason


def test_structural_invalidation_uses_larger_noise_buffer_once() -> None:
    geometry = build_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        invalidation_price=102.0,
        invalidation_type=InvalidationType.STRUCTURAL,
        atr=2.0,
    )

    assert geometry.buffer == pytest.approx(0.5)
    assert geometry.price == pytest.approx(102.5)
    assert "ATR" in geometry.buffer_reason


def test_strategy_buffered_invalidation_does_not_receive_another_buffer() -> None:
    geometry = build_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        invalidation_price=98.0,
        invalidation_type=InvalidationType.STRUCTURAL,
        atr=2.0,
        invalidation_already_buffered=True,
    )

    assert geometry.buffer == 0.0
    assert geometry.price == pytest.approx(98.0)
    assert "already includes" in geometry.buffer_reason


def test_strategy_buffered_invalidation_accepts_only_missing_runtime_top_up() -> None:
    geometry = build_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        invalidation_price=99.7,
        invalidation_type=InvalidationType.STRUCTURAL,
        atr=2.0,
        invalidation_already_buffered=True,
        execution_buffer_override=0.2,
    )

    assert geometry.buffer == pytest.approx(0.2)
    assert geometry.price == pytest.approx(99.5)
    assert "topped up" in geometry.buffer_reason


def test_runtime_execution_buffer_is_the_single_stop_buffer_authority() -> None:
    geometry = build_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        invalidation_price=102.0,
        invalidation_type=InvalidationType.STRUCTURAL,
        atr=2.0,
        execution_buffer_override=0.35,
    )

    assert geometry.buffer == pytest.approx(0.35)
    assert geometry.price == pytest.approx(102.35)
    assert "shared runtime" in geometry.buffer_reason


def test_layered_targets_do_not_invent_one_r_before_distant_structural_target() -> None:
    levels = build_layered_targets(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        stop_price=98.0,
        strategy_targets=(
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=106.0,
                label="primary",
                rationale=("nearest major resistance",),
            ),
        ),
    )

    assert [level.label for level in levels] == ["TP1"]
    assert levels[0].price == pytest.approx(106.0)
    assert levels[0].kind is TargetType.STRUCTURAL


def test_near_primary_target_is_not_split_artificially() -> None:
    levels = build_layered_targets(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        stop_price=102.0,
        strategy_targets=(
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=98.0,
                label="primary",
                rationale=("nearest support",),
            ),
        ),
    )

    assert len(levels) == 1
    assert levels[0].label == "TP1"
    assert levels[0].price == pytest.approx(98.0)
