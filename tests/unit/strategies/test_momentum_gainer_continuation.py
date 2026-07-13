from datetime import UTC, datetime

import pytest

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    FeatureSnapshot,
    MomentumGainerContinuationConfig,
    StrategyContext,
    StrategyType,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_momentum_gainer_continuation_candidates,
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


def _structure(*, bullish: bool, persistence: float = 0.8) -> StructureAnalysisResult:
    support = 98.0 if bullish else 94.0
    resistance = 106.0 if bullish else 102.0
    return StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH if bullish else TrendDirection.BEARISH,
            strength=0.85,
            evidence=TrendEvidence(persistence=persistence),
        ),
        levels=(
            StructureLevel(
                representative_price=support,
                low=support - 0.1,
                high=support + 0.1,
                role=LevelRole.SUPPORT,
                status=LevelStatus.ACTIVE,
                touches=2,
                pivot_indices=(1, 3),
                last_touch_index=3,
            ),
            StructureLevel(
                representative_price=resistance,
                low=resistance - 0.1,
                high=resistance + 0.1,
                role=LevelRole.RESISTANCE,
                status=LevelStatus.ACTIVE,
                touches=2,
                pivot_indices=(2, 4),
                last_touch_index=4,
            ),
        ),
    )


def _context(
    *,
    bullish: bool,
    roc: float | None = None,
    relative_volume: float = 1.6,
    persistence: float = 0.8,
    range_position: float | None = None,
    volatility_expansion: float = 0.5,
    higher_contradiction: bool = False,
) -> StrategyContext:
    sign = 1.0 if bullish else -1.0
    macro_bullish = not bullish if higher_contradiction else bullish
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="1h",
                role=TimeframeRole.MACRO,
                current_price=100.0,
                features=FeatureSnapshot(atr=4.0),
                structure=_structure(bullish=macro_bullish),
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
            ),
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=100.0,
                features=FeatureSnapshot(
                    atr=2.0,
                    ema_fast=99.5 if bullish else 100.5,
                    vwap=99.4 if bullish else 100.6,
                    rsi_slope=0.4 * sign,
                    macd_histogram=0.3 * sign,
                    rate_of_change=roc if roc is not None else 0.03 * sign,
                    relative_volume=relative_volume,
                    range_position=(0.75 if bullish else 0.25)
                    if range_position is None
                    else range_position,
                    volatility_expansion=volatility_expansion,
                ),
                structure=_structure(bullish=bullish, persistence=persistence),
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
            ),
        ),
    )


def test_generates_long_strong_mover_continuation() -> None:
    candidate = generate_momentum_gainer_continuation_candidates(
        _context(bullish=True), decision_time=NOW
    )[0]

    assert candidate.strategy is StrategyType.MOMENTUM_GAINER_CONTINUATION
    assert candidate.direction is TradeDirection.LONG
    assert candidate.metadata["expansion_roc"] == pytest.approx(0.03)
    assert candidate.invalidation.price < candidate.entry.lower
    assert candidate.targets.levels[0].price > candidate.entry.upper


def test_generates_short_strong_mover_continuation() -> None:
    candidate = generate_momentum_gainer_continuation_candidates(
        _context(bullish=False), decision_time=NOW
    )[0]

    assert candidate.direction is TradeDirection.SHORT
    assert candidate.invalidation.price > candidate.entry.upper
    assert candidate.targets.levels[0].price < candidate.entry.lower


def test_rejects_expansion_below_boundary() -> None:
    config = MomentumGainerContinuationConfig(minimum_absolute_roc=0.02)

    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, roc=0.0199), decision_time=NOW, config=config
        )
        == ()
    )
    assert generate_momentum_gainer_continuation_candidates(
        _context(bullish=True, roc=0.02), decision_time=NOW, config=config
    )


def test_rejects_insufficient_relative_volume() -> None:
    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, relative_volume=1.24), decision_time=NOW
        )
        == ()
    )


def test_rejects_weak_persistence() -> None:
    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, persistence=0.64), decision_time=NOW
        )
        == ()
    )


def test_rejects_disorderly_location_and_extension() -> None:
    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, range_position=0.59), decision_time=NOW
        )
        == ()
    )
    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, volatility_expansion=0.86), decision_time=NOW
        )
        == ()
    )


def test_rejects_higher_timeframe_contradiction() -> None:
    assert (
        generate_momentum_gainer_continuation_candidates(
            _context(bullish=True, higher_contradiction=True), decision_time=NOW
        )
        == ()
    )


def test_configuration_validates_boundaries() -> None:
    with pytest.raises(ValueError, match="must not exceed one"):
        MomentumGainerContinuationConfig(minimum_trend_persistence=1.01)


def test_output_is_deterministic() -> None:
    context = _context(bullish=True)
    assert generate_momentum_gainer_continuation_candidates(
        context, decision_time=NOW
    ) == generate_momentum_gainer_continuation_candidates(context, decision_time=NOW)
