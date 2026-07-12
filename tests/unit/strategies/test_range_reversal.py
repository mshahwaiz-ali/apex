from datetime import UTC, datetime

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_range_reversal_candidates,
)
from apex.structure.contracts import (
    RangeBreakoutState,
    RangeStructure,
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _context(
    *,
    bullish: bool,
    active: bool = False,
    sparse: bool = False,
    breakout_state: RangeBreakoutState = RangeBreakoutState.NONE,
    quality: float = 0.8,
) -> StrategyContext:
    current = 92.0 if bullish else 108.0
    position = 0.1 if bullish else 0.9
    features = (
        FeatureSnapshot(atr=2.0, range_position=position)
        if sparse
        else FeatureSnapshot(
            atr=2.0,
            range_position=position,
            rsi=42.0 if bullish else 58.0,
            rsi_slope=0.3 if bullish else -0.3,
            macd_histogram=0.2 if bullish else -0.2,
            rate_of_change=0.1 if bullish else -0.1,
            relative_volume=1.1,
        )
    )
    detected_range = RangeStructure(
        low=90.0,
        high=110.0,
        midpoint=100.0,
        width=20.0,
        width_percentage=20.0 / 100.0,
        start_index=1,
        end_index=20,
        upper_tests=3,
        lower_tests=3,
        breakout_state=breakout_state,
        current_position=position,
        quality=quality,
    )
    structure = StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.RANGE,
            strength=0.7,
            evidence=TrendEvidence(persistence=0.7),
        ),
        ranges=(detected_range,),
    )
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="15m",
                role=TimeframeRole.SETUP,
                current_price=current,
                features=features,
                structure=structure,
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
                active_candle=active,
            ),
        ),
    )


def test_generates_long_range_reversal() -> None:
    candidates = generate_range_reversal_candidates(
        _context(bullish=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.invalidation.price < candidate.entry.lower
    assert tuple(level.label for level in candidate.targets.levels) == (
        "midpoint",
        "opposite_boundary",
    )
    assert all(level.price > candidate.entry.upper for level in candidate.targets.levels)


def test_generates_short_range_reversal() -> None:
    candidates = generate_range_reversal_candidates(
        _context(bullish=False),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.SHORT
    assert candidate.invalidation.price > candidate.entry.upper
    assert all(level.price < candidate.entry.lower for level in candidate.targets.levels)


def test_rejects_directional_breakout_against_mean_reversion() -> None:
    assert (
        generate_range_reversal_candidates(
            _context(
                bullish=True,
                breakout_state=RangeBreakoutState.BEARISH,
            ),
            decision_time=NOW,
        )
        == ()
    )


def test_rejects_low_quality_range() -> None:
    assert (
        generate_range_reversal_candidates(
            _context(bullish=True, quality=0.4),
            decision_time=NOW,
        )
        == ()
    )


def test_tolerates_missing_optional_indicators() -> None:
    candidates = generate_range_reversal_candidates(
        _context(bullish=True, sparse=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].quality.momentum_quality == 0.5


def test_marks_active_candle_candidate_provisional() -> None:
    candidate = generate_range_reversal_candidates(
        _context(bullish=True, active=True),
        decision_time=NOW,
    )[0]

    assert candidate.provisional is True
    assert "active-candle evidence is provisional" in candidate.evidence.warnings


def test_output_is_deterministic() -> None:
    context = _context(bullish=True)

    first = generate_range_reversal_candidates(context, decision_time=NOW)
    second = generate_range_reversal_candidates(context, decision_time=NOW)

    assert first == second
