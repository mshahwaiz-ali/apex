from __future__ import annotations

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import TargetType, TradeDirection
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


def _level(
    low: float,
    high: float,
    *,
    role: LevelRole,
    touches: int,
    index: int,
) -> StructureLevel:
    return StructureLevel(
        representative_price=(low + high) / 2,
        low=low,
        high=high,
        role=role,
        status=LevelStatus.ACTIVE,
        touches=touches,
        pivot_indices=tuple(range(index, index + touches)),
        last_touch_index=index + touches - 1,
    )


def _frame(
    timeframe: str,
    role: TimeframeRole,
    *,
    atr: float,
    levels: tuple[StructureLevel, ...],
) -> TimeframeContext:
    structure = StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH,
            strength=0.8,
            evidence=TrendEvidence(),
        ),
        levels=tuple(
            sorted(
                levels,
                key=lambda level: (
                    level.representative_price,
                    level.role.value,
                    level.last_touch_index,
                ),
            )
        ),
    )
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=100.0,
        features=FeatureSnapshot(atr=atr),
        structure=structure,
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        exchange_tick_size=0.01,
    )


def test_long_target_ladder_uses_nearest_obstacles_across_timeframes() -> None:
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame(
                "15m",
                TimeframeRole.INTRADAY,
                atr=2.0,
                levels=(
                    _level(
                        108.0,
                        109.0,
                        role=LevelRole.RESISTANCE,
                        touches=3,
                        index=20,
                    ),
                ),
            ),
            _frame(
                "5m",
                TimeframeRole.SETUP,
                atr=1.0,
                levels=(
                    _level(
                        104.0,
                        104.5,
                        role=LevelRole.RESISTANCE,
                        touches=2,
                        index=10,
                    ),
                ),
            ),
            _frame(
                "3m",
                TimeframeRole.ENTRY,
                atr=0.5,
                levels=(
                    _level(
                        102.0,
                        102.2,
                        role=LevelRole.RESISTANCE,
                        touches=2,
                        index=5,
                    ),
                ),
            ),
        ),
    )

    targets = build_structural_target_ladder(context, direction=TradeDirection.LONG)

    assert [target.label for target in targets] == ["tp1", "tp2", "tp3"]
    assert [target.kind for target in targets] == [
        TargetType.STRUCTURAL,
        TargetType.STRUCTURAL,
        TargetType.STRUCTURAL,
    ]
    assert targets[0].price < 102.0
    assert targets[1].price < 104.0
    assert targets[2].price < 108.0
    assert targets[0].price < targets[1].price < targets[2].price
    assert "3m opposing resistance zone" in targets[0].rationale[0]
    assert "5m opposing resistance zone" in targets[1].rationale[0]
    assert "15m opposing resistance zone" in targets[2].rationale[0]


def test_overlapping_timeframe_zones_are_deduplicated() -> None:
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame(
                "15m",
                TimeframeRole.INTRADAY,
                atr=2.0,
                levels=(
                    _level(
                        104.1,
                        104.6,
                        role=LevelRole.RESISTANCE,
                        touches=4,
                        index=20,
                    ),
                ),
            ),
            _frame(
                "5m",
                TimeframeRole.SETUP,
                atr=1.0,
                levels=(
                    _level(
                        104.0,
                        104.5,
                        role=LevelRole.RESISTANCE,
                        touches=2,
                        index=10,
                    ),
                ),
            ),
            _frame(
                "3m",
                TimeframeRole.ENTRY,
                atr=0.5,
                levels=(),
            ),
        ),
    )

    targets = build_structural_target_ladder(context, direction=TradeDirection.LONG)

    assert len(targets) == 1
    assert "5m opposing resistance zone" in targets[0].rationale[0]
