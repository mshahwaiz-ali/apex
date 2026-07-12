from datetime import UTC, datetime

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    STRATEGY_REGISTRY,
    FeatureSnapshot,
    StrategyContext,
    StrategyType,
    TimeframeContext,
    TimeframeRole,
    analyze_phase4,
)
from apex.structure.contracts import (
    LevelRole,
    LevelStatus,
    StructureAnalysisResult,
    StructureLevel,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _structure(*, bullish: bool) -> StructureAnalysisResult:
    levels = (
        StructureLevel(
            representative_price=98.0,
            low=97.9,
            high=98.1,
            role=LevelRole.SUPPORT,
            status=LevelStatus.ACTIVE,
            touches=1,
            pivot_indices=(1,),
            last_touch_index=1,
        ),
        StructureLevel(
            representative_price=106.0,
            low=105.9,
            high=106.1,
            role=LevelRole.RESISTANCE,
            status=LevelStatus.ACTIVE,
            touches=1,
            pivot_indices=(2,),
            last_touch_index=2,
        ),
    )
    return StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH if bullish else TrendDirection.BEARISH,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
        levels=levels,
    )


def _context(*, actionable: bool) -> StrategyContext:
    structure = _structure(bullish=True)
    features = (
        FeatureSnapshot(
            atr=2.0,
            ema_fast=99.5,
            ema_slow=98.5,
            vwap=99.2,
            rsi=55.0,
            rsi_slope=0.3,
            macd_histogram=0.2,
            rate_of_change=0.25,
            relative_volume=1.2,
        )
        if actionable
        else FeatureSnapshot(atr=2.0)
    )
    if not actionable:
        structure = StructureAnalysisResult(
            swings=(),
            trend=TrendAnalysis(
                direction=TrendDirection.UNCERTAIN,
                strength=0.2,
                evidence=TrendEvidence(persistence=0.2),
            ),
        )
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=100.0,
                features=features,
                structure=structure,
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
            ),
        ),
    )


def test_registry_has_fixed_expected_order() -> None:
    assert tuple(strategy for strategy, _generator in STRATEGY_REGISTRY) == (
        StrategyType.TREND_PULLBACK,
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.LIQUIDITY_REVERSAL,
        StrategyType.RANGE_REVERSAL,
        StrategyType.MOMENTUM_CONTINUATION,
    )


def test_empty_context_produces_no_candidates() -> None:
    result = analyze_phase4(_context(actionable=False), decision_time=NOW)

    assert result.candidates == ()


def test_competing_candidates_are_retained_in_registry_order() -> None:
    result = analyze_phase4(_context(actionable=True), decision_time=NOW)

    strategies = tuple(candidate.strategy for candidate in result.candidates)
    assert StrategyType.TREND_PULLBACK in strategies
    assert StrategyType.MOMENTUM_CONTINUATION in strategies
    assert strategies.index(StrategyType.TREND_PULLBACK) < strategies.index(
        StrategyType.MOMENTUM_CONTINUATION
    )


def test_repeated_analysis_is_deterministic_and_does_not_mutate_context() -> None:
    context = _context(actionable=True)
    original_frames = context.frames

    first = analyze_phase4(context, decision_time=NOW)
    second = analyze_phase4(context, decision_time=NOW)

    assert first == second
    assert context.frames == original_frames
