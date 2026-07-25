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


def _level(low: float, high: float, *, timeframe_index: int) -> StructureLevel:
    return StructureLevel(
        representative_price=(low + high) / 2,
        low=low,
        high=high,
        role=LevelRole.RESISTANCE,
        status=LevelStatus.ACTIVE,
        touches=2,
        pivot_indices=(timeframe_index, timeframe_index + 1),
        last_touch_index=timeframe_index + 1,
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


def _candidate() -> TradeCandidate:
    return TradeCandidate(
        symbol="TEST/USDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 25, tzinfo=UTC),
        entry=EntryZone(
            lower=99.8,
            upper=100.0,
            preferred=99.9,
            current_price=100.0,
            distance_from_current=0.1,
            atr_distance=0.1,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
            max_chase_price=100.2,
        ),
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
                    rationale=("distant measured expansion",),
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
        layered_state=LayeredStateSnapshot(),
        score_dimensions=ScoreDimensions(),
    )


def test_all_strategy_targets_are_reordered_behind_nearer_obstacles() -> None:
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame("15m", TimeframeRole.INTRADAY, atr=2.0, levels=(_level(108, 109, timeframe_index=20),)),
            _frame("5m", TimeframeRole.SETUP, atr=1.0, levels=(_level(104, 104.5, timeframe_index=10),)),
            _frame("3m", TimeframeRole.ENTRY, atr=0.5, levels=(_level(102, 102.2, timeframe_index=5),)),
        ),
    )

    candidate = apply_target_ladder_to_candidates(context, (_candidate(),))[0]

    assert [level.label for level in candidate.targets.levels] == ["tp1", "tp2", "tp3"]
    assert [level.kind for level in candidate.targets.levels] == [
        TargetType.STRUCTURAL,
        TargetType.STRUCTURAL,
        TargetType.STRUCTURAL,
    ]
    assert candidate.targets.levels[0].price < candidate.targets.levels[1].price
    assert candidate.targets.levels[1].price < candidate.targets.levels[2].price
    assert candidate.targets.levels[-1].price < 110.0
    assert candidate.metadata["target_ladder_scope"] == "all_strategy_families"
    assert candidate.metadata["target_1_timeframe"] == "3m"
    assert candidate.metadata["target_2_timeframe"] == "5m"
    assert candidate.metadata["target_3_timeframe"] == "15m"
