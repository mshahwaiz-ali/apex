from datetime import UTC, datetime

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_momentum_continuation_candidates,
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


def _context(
    *,
    bullish: bool,
    active: bool = False,
    sparse: bool = False,
    contradictory_momentum: bool = False,
    higher_timeframe_contradiction: bool = False,
) -> StrategyContext:
    sign = 1.0 if bullish else -1.0
    if contradictory_momentum:
        sign *= -1.0
    features = (
        FeatureSnapshot(
            atr=2.0,
            rate_of_change=0.25 * sign,
        )
        if sparse
        else FeatureSnapshot(
            atr=2.0,
            ema_fast=99.5 if bullish else 100.5,
            vwap=99.2 if bullish else 100.8,
            rsi=55.0 if bullish else 45.0,
            rsi_slope=0.3 * sign,
            macd_histogram=0.2 * sign,
            rate_of_change=0.25 * sign,
            relative_volume=1.3,
        )
    )
    macro_bullish = not bullish if higher_timeframe_contradiction else bullish
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="4h",
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
                features=features,
                structure=_structure(bullish=bullish),
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
                active_candle=active,
            ),
        ),
    )


def test_generates_long_momentum_continuation() -> None:
    candidates = generate_momentum_continuation_candidates(
        _context(bullish=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.invalidation.price < candidate.entry.lower
    assert candidate.targets.levels[0].price > candidate.entry.upper


def test_generates_short_momentum_continuation() -> None:
    candidates = generate_momentum_continuation_candidates(
        _context(bullish=False),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.SHORT
    assert candidate.invalidation.price > candidate.entry.upper
    assert candidate.targets.levels[0].price < candidate.entry.lower


def test_tolerates_missing_optional_indicators() -> None:
    candidates = generate_momentum_continuation_candidates(
        _context(bullish=True, sparse=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].quality.momentum_quality == 1.0


def test_rejects_contradictory_momentum() -> None:
    assert (
        generate_momentum_continuation_candidates(
            _context(bullish=True, contradictory_momentum=True),
            decision_time=NOW,
        )
        == ()
    )


def test_rejects_higher_timeframe_contradiction() -> None:
    assert (
        generate_momentum_continuation_candidates(
            _context(bullish=True, higher_timeframe_contradiction=True),
            decision_time=NOW,
        )
        == ()
    )


def test_marks_active_candle_candidate_provisional() -> None:
    candidate = generate_momentum_continuation_candidates(
        _context(bullish=True, active=True),
        decision_time=NOW,
    )[0]

    assert candidate.provisional is True
    assert "active-candle evidence is provisional" in candidate.evidence.warnings


def test_output_is_deterministic() -> None:
    context = _context(bullish=True)

    first = generate_momentum_continuation_candidates(context, decision_time=NOW)
    second = generate_momentum_continuation_candidates(context, decision_time=NOW)

    assert first == second
