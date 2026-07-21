from __future__ import annotations

import pytest

from apex.application.trade_geometry import build_layered_targets
from apex.strategies.contracts import TargetLevel, TargetType, TradeDirection


def _target(price: float, *, kind: TargetType, label: str) -> TargetLevel:
    return TargetLevel(
        kind=kind,
        price=price,
        label=label,
        rationale=(f"{kind.value} target",),
    )


def test_one_valid_target_is_accepted_as_tp1() -> None:
    targets = build_layered_targets(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        stop_price=98.0,
        strategy_targets=(_target(103.0, kind=TargetType.STRUCTURAL, label="structure"),),
    )
    assert len(targets) == 1
    assert targets[0].label == "TP1"
    assert targets[0].price == 103.0


def test_wrong_direction_targets_are_removed() -> None:
    targets = build_layered_targets(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        stop_price=102.0,
        strategy_targets=(
            _target(103.0, kind=TargetType.STRUCTURAL, label="wrong"),
            _target(97.0, kind=TargetType.LIQUIDITY, label="valid"),
        ),
    )
    assert tuple(target.price for target in targets) == (97.0,)


def test_all_wrong_direction_targets_are_rejected() -> None:
    with pytest.raises(ValueError, match="directionally valid target"):
        build_layered_targets(
            direction=TradeDirection.LONG,
            preferred_entry=100.0,
            stop_price=98.0,
            strategy_targets=(_target(99.0, kind=TargetType.STRUCTURAL, label="wrong"),),
        )


def test_duplicate_targets_are_deduplicated_by_tick_size() -> None:
    targets = build_layered_targets(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        stop_price=98.0,
        tick_size=0.01,
        strategy_targets=(
            _target(103.000, kind=TargetType.LIQUIDITY, label="liquidity"),
            _target(103.006, kind=TargetType.STRUCTURAL, label="structure"),
            _target(106.0, kind=TargetType.RANGE, label="range"),
        ),
    )
    assert tuple(target.price for target in targets) == (103.006, 106.0)
    assert targets[0].kind is TargetType.STRUCTURAL


def test_source_hierarchy_decides_duplicate_survivor() -> None:
    targets = build_layered_targets(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        stop_price=98.0,
        tick_size=0.01,
        strategy_targets=(
            _target(104.0, kind=TargetType.EXPANSION, label="expansion"),
            _target(104.0, kind=TargetType.STRUCTURAL, label="structure"),
        ),
    )
    assert targets[0].kind is TargetType.STRUCTURAL


def test_targets_are_ordered_and_capped_at_three() -> None:
    targets = build_layered_targets(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        stop_price=102.0,
        strategy_targets=(
            _target(90.0, kind=TargetType.EXPANSION, label="far"),
            _target(98.0, kind=TargetType.STRUCTURAL, label="near"),
            _target(95.0, kind=TargetType.LIQUIDITY, label="middle"),
            _target(92.0, kind=TargetType.RANGE, label="fourth"),
        ),
    )
    assert tuple(target.price for target in targets) == (98.0, 95.0, 92.0)
    assert tuple(target.label for target in targets) == ("TP1", "TP2", "TP3")


def test_invalid_tick_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="tick size must be positive"):
        build_layered_targets(
            direction=TradeDirection.LONG,
            preferred_entry=100.0,
            stop_price=98.0,
            tick_size=0.0,
            strategy_targets=(_target(103.0, kind=TargetType.STRUCTURAL, label="structure"),),
        )
