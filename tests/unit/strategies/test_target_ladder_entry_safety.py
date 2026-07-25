from __future__ import annotations

from datetime import UTC, datetime

from apex.domain.methodology_contracts import LayeredStateSnapshot, ScoreDimensions
from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import (
    EntryMode,
    EntryZone,
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
from apex.strategies.strategy_types import StrategyType
from apex.strategies.target_ladder import apply_target_ladder_to_candidates
from apex.structure.contracts import (
    LevelRole,
    LevelStatus,
    StructureAnalysisResult,
    StructureLevel,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)


def _level(low: float, high: float, *, index: int) -> StructureLevel:
    return StructureLevel(
        representative_price=(low + high) / 2,
        low=low,
        high=high,
        role=LevelRole.RESISTANCE,
        status=LevelStatus.ACTIVE,
        touches=2,
        pivot_indices=(index, index + 1),
        last_touch_index=index + 1,
    )


def _frame(
    timeframe: str,
    role: TimeframeRole,
    *,
    atr: float,
    levels: tuple[StructureLevel, ...],
) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=100.0,
        features=FeatureSnapshot(atr=atr),
        structure=StructureAnalysisResult(
            swings=(),
            trend=TrendAnalysis(
                direction=TrendDirection.BULLISH,
                strength=0.8,
                evidence=TrendEvidence(),
            ),
            levels=levels,
        ),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        exchange_tick_size=0.01,
    )


def _candidate(entry: EntryZone) -> TradeCandidate:
    return TradeCandidate(
        symbol="TEST/USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 25, tzinfo=UTC),
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.5,
            rationale=("test invalidation",),
        ),
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
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
            extension_penalty=0.0,
            conflict_penalty=0.0,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={"decision_timeframe": "3m", "decision_atr": 0.5},
        entry_opportunities=(entry,),
        layered_state=LayeredStateSnapshot(),
        score_dimensions=ScoreDimensions(),
    )


def test_structural_obstacle_inside_future_entry_zone_is_not_published() -> None:
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
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame(
                "5m",
                TimeframeRole.SETUP,
                atr=1.0,
                levels=(_level(101.1, 101.4, index=10),),
            ),
            _frame(
                "3m",
                TimeframeRole.ENTRY,
                atr=0.5,
                levels=(_level(103.0, 103.4, index=5),),
            ),
        ),
    )

    updated = apply_target_ladder_to_candidates(context, (_candidate(future_entry),))[0]

    assert all(level.price > future_entry.upper for level in updated.targets.levels)
    assert updated.targets.levels[0].price > 102.0
