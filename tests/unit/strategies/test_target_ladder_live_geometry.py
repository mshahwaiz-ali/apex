from __future__ import annotations

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.target_ladder import build_structural_target_ladder
from apex.structure.contracts import (
    LevelRole,
    LevelStatus,
    StructureAnalysisResult,
    StructureLevel,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)


def _level(price: float) -> StructureLevel:
    return StructureLevel(
        representative_price=price,
        low=price,
        high=price,
        role=LevelRole.RESISTANCE,
        status=LevelStatus.ACTIVE,
        touches=2,
        pivot_indices=(1, 2),
        last_touch_index=2,
    )


def _frame(
    timeframe: str,
    role: TimeframeRole,
    *,
    current: float,
    atr: float,
    tick_size: float,
    level_price: float,
) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=current,
        features=FeatureSnapshot(atr=atr),
        structure=StructureAnalysisResult(
            swings=(),
            trend=TrendAnalysis(
                direction=TrendDirection.BULLISH,
                strength=0.8,
                evidence=TrendEvidence(),
            ),
            levels=(_level(level_price),),
        ),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        exchange_tick_size=tick_size,
    )


def test_oversized_exchange_tick_does_not_become_front_run_buffer() -> None:
    context = StrategyContext(
        symbol="STAR/USDT",
        frames=(
            _frame(
                "1h",
                TimeframeRole.INTRADAY,
                current=0.1201,
                atr=0.001,
                tick_size=0.1,
                level_price=0.125,
            ),
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                current=0.1201,
                atr=0.001,
                tick_size=0.1,
                level_price=0.125,
            ),
        ),
    )

    targets = build_structural_target_ladder(
        context,
        direction=TradeDirection.LONG,
        max_distance_atr=8.0,
    )

    assert len(targets) == 1
    assert 0.124 < targets[0].price < 0.125
    assert abs(targets[0].price - 0.125) <= 0.00015


def test_countertrend_scope_can_exclude_distant_four_hour_structure() -> None:
    context = StrategyContext(
        symbol="LAB/USDT",
        frames=(
            _frame(
                "4h",
                TimeframeRole.INTERMEDIATE,
                current=0.1597,
                atr=0.001,
                tick_size=0.0001,
                level_price=0.2688,
            ),
            _frame(
                "5m",
                TimeframeRole.ENTRY,
                current=0.1597,
                atr=0.001,
                tick_size=0.0001,
                level_price=0.165,
            ),
        ),
    )

    targets = build_structural_target_ladder(
        context,
        direction=TradeDirection.LONG,
        max_distance_atr=8.0,
        max_timeframe_minutes=15,
    )

    assert len(targets) == 1
    assert "5m opposing resistance" in targets[0].rationale[0]
    assert targets[0].price < 0.165
