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
