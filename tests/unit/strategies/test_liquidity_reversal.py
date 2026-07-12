from datetime import UTC, datetime

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.liquidity.contracts import (
    LiquiditySide,
    LiquiditySweep,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
    SweepClassification,
    TrapEvent,
    TrapType,
)
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_liquidity_reversal_candidates,
)
from apex.structure.contracts import (
    BreakDirection,
    ConfirmationStatus,
    LevelRole,
    LevelStatus,
    StructureAnalysisResult,
    StructureLevel,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _zone(*, bullish: bool) -> LiquidityZone:
    return LiquidityZone(
        side=LiquiditySide.SELL_SIDE if bullish else LiquiditySide.BUY_SIDE,
        kind=LiquidityZoneType.EQUAL_LOWS if bullish else LiquidityZoneType.EQUAL_HIGHS,
        low=98.0 if bullish else 101.0,
        high=99.0 if bullish else 102.0,
        representative_price=98.5 if bullish else 101.5,
        source_pivot_indices=(1, 2),
        touch_count=2,
        created_index=1,
        last_touch_index=2,
        age=3,
        status=LiquidityZoneStatus.SWEPT,
        strength=0.8,
    )


def _sweep(
    *,
    bullish: bool,
    confirmed: bool = True,
) -> LiquiditySweep:
    zone = _zone(bullish=bullish)
    return LiquiditySweep(
        zone=zone,
        direction=BreakDirection.BEARISH if bullish else BreakDirection.BULLISH,
        candle_index=5,
        candle_time=NOW,
        penetration=0.5,
        close_recovery=0.8,
        classification=(
            SweepClassification.CONFIRMED_SWEEP
            if confirmed
            else SweepClassification.DEVELOPING_SWEEP
        ),
        confirmation=(
            ConfirmationStatus.CONFIRMED
            if confirmed
            else ConfirmationStatus.DEVELOPING
        ),
        evidence=("liquidity breach recovered",),
    )


def _trap(
    *,
    bullish: bool,
    sweep: LiquiditySweep,
    confirmed: bool = True,
) -> TrapEvent:
    return TrapEvent(
        kind=TrapType.BEAR_TRAP if bullish else TrapType.BULL_TRAP,
        candle_index=sweep.candle_index,
        candle_time=sweep.candle_time,
        zone=sweep.zone,
        sweep=sweep,
        confirmation=(
            ConfirmationStatus.CONFIRMED
            if confirmed
            else ConfirmationStatus.DEVELOPING
        ),
        evidence=("rejection follow-through confirmed",),
        invalidation=("price closes beyond swept liquidity",),
    )


def _structure(*, bullish: bool) -> StructureAnalysisResult:
    levels = (
        StructureLevel(
            representative_price=94.0,
            low=93.9,
            high=94.1,
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
            direction=TrendDirection.WEAK_BULLISH if bullish else TrendDirection.WEAK_BEARISH,
            strength=0.55,
            evidence=TrendEvidence(persistence=0.5),
        ),
        levels=levels,
    )


def _context(
    *,
    bullish: bool,
    sweep_confirmed: bool = True,
    trap_confirmed: bool = True,
    active: bool = False,
) -> StrategyContext:
    sweep = _sweep(bullish=bullish, confirmed=sweep_confirmed)
    trap = _trap(bullish=bullish, sweep=sweep, confirmed=trap_confirmed)
    features = FeatureSnapshot(
        atr=2.0,
        rsi=42.0 if bullish else 58.0,
        rsi_slope=0.3 if bullish else -0.3,
        macd_histogram=0.2 if bullish else -0.2,
        rate_of_change=0.1 if bullish else -0.1,
        relative_volume=1.4,
    )
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=100.0,
                features=features,
                structure=_structure(bullish=bullish),
                liquidity=LiquidityAnalysisResult(
                    zones=(sweep.zone,),
                    sweeps=(sweep,),
                    traps=(trap,),
                ),
                active_candle=active,
            ),
        ),
    )


def test_generates_long_after_confirmed_sell_side_sweep() -> None:
    candidates = generate_liquidity_reversal_candidates(
        _context(bullish=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.entry.preferred == 99.0
    assert candidate.invalidation.price < candidate.entry.lower
    assert candidate.targets.levels[0].price == 106.0


def test_generates_short_after_confirmed_buy_side_sweep() -> None:
    candidates = generate_liquidity_reversal_candidates(
        _context(bullish=False),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.SHORT
    assert candidate.entry.preferred == 101.0
    assert candidate.invalidation.price > candidate.entry.upper
    assert candidate.targets.levels[0].price == 94.0


def test_rejects_developing_sweep() -> None:
    candidates = generate_liquidity_reversal_candidates(
        _context(bullish=True, sweep_confirmed=False),
        decision_time=NOW,
    )

    assert candidates == ()


def test_rejects_unconfirmed_trap() -> None:
    candidates = generate_liquidity_reversal_candidates(
        _context(bullish=True, trap_confirmed=False),
        decision_time=NOW,
    )

    assert candidates == ()


def test_marks_active_candle_candidate_provisional() -> None:
    candidate = generate_liquidity_reversal_candidates(
        _context(bullish=True, active=True),
        decision_time=NOW,
    )[0]

    assert candidate.provisional is True
    assert "active-candle evidence is provisional" in candidate.evidence.warnings
