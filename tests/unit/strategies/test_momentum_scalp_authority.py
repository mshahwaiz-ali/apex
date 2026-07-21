from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apex.domain.models import Candle
from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.momentum_continuation import (
    _directional_rejection_after_impulse,
    _immediate_timeframe_authority,
    _lower_timeframe_trigger,
    _recent_continuation_break_age,
)
from apex.strategies.momentum_scalp import _scalp_targets
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ConfirmationStatus,
    LevelRole,
    LevelStatus,
    PivotStatus,
    StructureAnalysisResult,
    StructureBreak,
    StructureLevel,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

NOW = datetime(2026, 7, 22, tzinfo=UTC)


def _candles(*, rejected: bool = False) -> tuple[Candle, ...]:
    prices = ((100.0, 100.8), (100.8, 101.4), (101.4, 101.8), (101.8, 101.9))
    result: list[Candle] = []
    for index, (open_price, close_price) in enumerate(prices):
        high = max(open_price, close_price) + (1.0 if rejected and index == 3 else 0.1)
        low = min(open_price, close_price) - 0.1
        open_time = NOW + timedelta(minutes=index * 5)
        result.append(
            Candle(
                symbol="TESTUSDT",
                timeframe="5m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=5),
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=1_000.0,
                is_closed=True,
                source="test",
            )
        )
    return tuple(result)


def _structure(
    direction: TrendDirection,
    *,
    break_index: int | None = None,
    level: tuple[LevelRole, float] | None = None,
) -> StructureAnalysisResult:
    swing = SwingPoint(
        index=0,
        time=NOW,
        price=100.5,
        kind=SwingType.HIGH,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )
    breaks = ()
    if break_index is not None:
        breaks = (
            StructureBreak(
                direction=BreakDirection.BULLISH,
                broken_swing=swing,
                candle_index=break_index,
                candle_time=NOW + timedelta(minutes=break_index * 5),
                broken_level=100.5,
                close_distance=0.5,
                wick_penetration=0.1,
                quality=BreakQuality.VALID,
                confirmation=ConfirmationStatus.CONFIRMED,
            ),
        )
    levels = ()
    if level is not None:
        role, price = level
        levels = (
            StructureLevel(
                representative_price=price,
                low=price * 0.999,
                high=price * 1.001,
                role=role,
                status=LevelStatus.ACTIVE,
                touches=1,
                pivot_indices=(1,),
                last_touch_index=1,
            ),
        )
    return StructureAnalysisResult(
        swings=(swing,),
        trend=TrendAnalysis(
            direction=direction,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
        breaks=breaks,
        levels=levels,
    )


def _frame(
    role: TimeframeRole,
    direction: TrendDirection,
    *,
    timeframe: str,
    break_index: int | None = None,
    level: tuple[LevelRole, float] | None = None,
    rejected: bool = False,
) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=101.9,
        features=FeatureSnapshot(atr=1.0, ema_fast=101.0, vwap=100.8),
        structure=_structure(direction, break_index=break_index, level=level),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        recent_candles=_candles(rejected=rejected),
    )


def _context(*frames: TimeframeContext) -> StrategyContext:
    return StrategyContext(symbol="TESTUSDT", frames=frames)


def test_15m_alignment_confirms_but_30m_opposition_blocks_immediate_entry() -> None:
    aligned = _context(
        _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH, timeframe="30m"),
        _frame(TimeframeRole.SETUP, TrendDirection.BULLISH, timeframe="15m"),
        _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, timeframe="5m"),
    )
    opposed = _context(
        _frame(TimeframeRole.INTRADAY, TrendDirection.BEARISH, timeframe="30m"),
        _frame(TimeframeRole.SETUP, TrendDirection.BULLISH, timeframe="15m"),
        _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, timeframe="5m"),
    )

    assert _immediate_timeframe_authority(aligned, bullish=True) == (True, False)
    assert _immediate_timeframe_authority(opposed, bullish=True) == (True, True)


def test_3m_confirms_trigger_while_opposing_1m_blocks_timing() -> None:
    confirmed = _context(
        _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, timeframe="5m"),
        _frame(TimeframeRole.REFINEMENT, TrendDirection.BULLISH, timeframe="3m"),
        _frame(TimeframeRole.TIMING, TrendDirection.BULLISH, timeframe="1m"),
    )
    opposed = _context(
        _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, timeframe="5m"),
        _frame(TimeframeRole.REFINEMENT, TrendDirection.BULLISH, timeframe="3m"),
        _frame(TimeframeRole.TIMING, TrendDirection.BEARISH, timeframe="1m"),
    )

    assert _lower_timeframe_trigger(confirmed, bullish=True) == (True, False)
    assert _lower_timeframe_trigger(opposed, bullish=True) == (True, True)


def test_break_must_be_recent_and_remain_held() -> None:
    fresh = _context(
        _frame(
            TimeframeRole.ENTRY,
            TrendDirection.BULLISH,
            timeframe="5m",
            break_index=2,
        )
    )
    stale = _context(
        _frame(
            TimeframeRole.ENTRY,
            TrendDirection.BULLISH,
            timeframe="5m",
            break_index=1,
        )
    )

    assert _recent_continuation_break_age(fresh, bullish=True, maximum_age_bars=1) == 1
    assert _recent_continuation_break_age(stale, bullish=True, maximum_age_bars=1) is None


def test_atr_sized_pump_with_large_rejection_wick_is_blocked() -> None:
    context = _context(
        _frame(
            TimeframeRole.ENTRY,
            TrendDirection.BULLISH,
            timeframe="5m",
            rejected=True,
        )
    )

    assert _directional_rejection_after_impulse(context, bullish=True) is True


def test_scalp_requires_microstructure_tp1_and_uses_15m_only_as_tp2() -> None:
    context = _context(
        _frame(
            TimeframeRole.SETUP,
            TrendDirection.BULLISH,
            timeframe="15m",
            level=(LevelRole.RESISTANCE, 103.0),
        ),
        _frame(
            TimeframeRole.ENTRY,
            TrendDirection.BULLISH,
            timeframe="5m",
            level=(LevelRole.RESISTANCE, 102.2),
        ),
    )
    candidate = SimpleNamespace(
        direction=TradeDirection.LONG,
        entry=SimpleNamespace(preferred=101.9),
    )

    targets = _scalp_targets(candidate, context=context)  # type: ignore[arg-type]

    assert [target.price for target in targets] == [102.2, 103.0]
    assert targets[0].rationale[0] == "nearest verified 1m/3m/5m opposing structure"


def test_scalp_without_verified_microstructure_target_is_rejected() -> None:
    context = _context(_frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, timeframe="5m"))
    candidate = SimpleNamespace(
        direction=TradeDirection.LONG,
        entry=SimpleNamespace(preferred=101.9),
    )

    assert _scalp_targets(candidate, context=context) == ()  # type: ignore[arg-type]
