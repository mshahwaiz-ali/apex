from __future__ import annotations

from dataclasses import replace

from apex.strategies.contracts import EntryMode, EntryZone, TargetConcept, TargetLevel, TargetType
from apex.strategies.target_ladder import apply_target_ladder_to_candidates

from .test_universal_target_ladder import _candidate, _frame, _level
from apex.strategies.context import StrategyContext, TimeframeRole


def test_structural_obstacle_inside_future_entry_zone_is_not_published() -> None:
    base = _candidate()
    future_entry = EntryZone(
        lower=101.0,
        upper=101.5,
        preferred=101.25,
        current_price=100.0,
        distance_from_current=1.25,
        atr_distance=2.5,
        estimated_move_missed=0.0,
        location_quality=0.7,
        mode=EntryMode.PULLBACK,
        rationale=("future pullback entry",),
        max_chase_price=101.7,
    )
    candidate = replace(
        base,
        entry=future_entry,
        entry_opportunities=(future_entry,),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.EXPANSION,
                    price=110.0,
                    label="primary",
                    rationale=("valid distant objective",),
                ),
            )
        ),
    )
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame(
                "5m",
                TimeframeRole.SETUP,
                atr=1.0,
                levels=(_level(101.1, 101.4, timeframe_index=10),),
            ),
            _frame(
                "3m",
                TimeframeRole.ENTRY,
                atr=0.5,
                levels=(_level(103.0, 103.4, timeframe_index=5),),
            ),
        ),
    )

    updated = apply_target_ladder_to_candidates(context, (candidate,))[0]

    assert all(level.price > future_entry.upper for level in updated.targets.levels)
    assert updated.targets.levels[0].price > 102.0
