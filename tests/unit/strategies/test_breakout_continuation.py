from datetime import UTC, datetime

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_breakout_continuation_candidates,
)
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    PivotStatus,
    StructureAnalysisResult,
    StructureBreak,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

_DECISION_TIME = datetime(2026, 7, 13, tzinfo=UTC)


def _structure(*, bullish: bool, quality: BreakQuality) -> StructureAnalysisResult:
    swing = SwingPoint(
        index=2,
        time=datetime(2026, 7, 12, 20, tzinfo=UTC),
        price=100.0,
        kind=SwingType.HIGH if bullish else SwingType.LOW,
        status=PivotStatus.CONFIRMED,
        left_window=2,
        right_window=2,
    )
    break_event = StructureBreak(
        direction=BreakDirection.BULLISH if bullish else BreakDirection.BEARISH,
        broken_swing=swing,
        candle_index=5,
        candle_time=_DECISION_TIME,
        broken_level=100.0,
        close_distance=0.004,
        wick_penetration=0.006,
        quality=quality,
        confirmation=ConfirmationStatus.CONFIRMED,
        evidence=("confirmed close beyond structure",),
    )
    return StructureAnalysisResult(
        swings=(swing,),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH if bullish else TrendDirection.BEARISH,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
        breaks=(break_event,),
    )


def _frame(
    *,
    bullish: bool,
    role: TimeframeRole,
    quality: BreakQuality = BreakQuality.VALID,
    current_price: float | None = None,
    relative_volume: float | None = 1.3,
    active: bool = False,
) -> TimeframeContext:
    price = current_price if current_price is not None else (101.0 if bullish else 99.0)
    return TimeframeContext(
        timeframe="4h" if role is TimeframeRole.MACRO else "5m",
        role=role,
        current_price=price,
        features=FeatureSnapshot(
            atr=2.0,
            relative_volume=relative_volume,
            macd_histogram=0.2 if bullish else -0.2,
        ),
        structure=_structure(bullish=bullish, quality=quality),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        active_candle=active,
    )


def _context(
    *,
    bullish: bool,
    quality: BreakQuality = BreakQuality.VALID,
    current_price: float | None = None,
    relative_volume: float | None = 1.3,
    higher_timeframe_contradiction: bool = False,
    active: bool = False,
) -> StrategyContext:
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            _frame(
                bullish=not bullish if higher_timeframe_contradiction else bullish,
                role=TimeframeRole.MACRO,
            ),
            _frame(
                bullish=bullish,
                role=TimeframeRole.ENTRY,
                quality=quality,
                current_price=current_price,
                relative_volume=relative_volume,
                active=active,
            ),
        ),
    )


def test_generates_long_breakout_retest_candidate() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True),
        decision_time=_DECISION_TIME,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.entry.preferred == 100.0
    assert candidate.invalidation.price < candidate.entry.lower
    assert candidate.targets.levels[0].price > candidate.entry.upper


def test_generates_short_breakout_retest_candidate() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=False),
        decision_time=_DECISION_TIME,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.SHORT
    assert candidate.entry.preferred == 100.0
    assert candidate.invalidation.price > candidate.entry.upper
    assert candidate.targets.levels[0].price < candidate.entry.lower


def test_rejects_weak_breakout() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True, quality=BreakQuality.WEAK),
        decision_time=_DECISION_TIME,
    )

    assert candidates == ()


def test_rejects_low_volume_when_volume_is_available() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True, relative_volume=0.7),
        decision_time=_DECISION_TIME,
    )

    assert candidates == ()


def test_allows_missing_optional_volume() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True, relative_volume=None),
        decision_time=_DECISION_TIME,
    )

    assert len(candidates) == 1
    assert candidates[0].quality.volume_quality == 0.5


def test_rejects_overextended_breakout() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True, current_price=104.0),
        decision_time=_DECISION_TIME,
    )

    assert candidates == ()


def test_rejects_higher_timeframe_contradiction() -> None:
    candidates = generate_breakout_continuation_candidates(
        _context(bullish=True, higher_timeframe_contradiction=True),
        decision_time=_DECISION_TIME,
    )

    assert candidates == ()


def test_marks_active_candle_candidate_provisional() -> None:
    candidate = generate_breakout_continuation_candidates(
        _context(bullish=True, active=True),
        decision_time=_DECISION_TIME,
    )[0]

    assert candidate.provisional is True
    assert "active-candle evidence is provisional" in candidate.evidence.warnings


def test_output_is_deterministic() -> None:
    context = _context(bullish=True)

    first = generate_breakout_continuation_candidates(
        context,
        decision_time=_DECISION_TIME,
    )
    second = generate_breakout_continuation_candidates(
        context,
        decision_time=_DECISION_TIME,
    )

    assert first == second
