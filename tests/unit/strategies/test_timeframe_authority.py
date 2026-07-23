"""Regression coverage for deterministic breakout timeframe authority."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from apex.strategies.context import StrategyContext, TimeframeContext, TimeframeRole
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
from apex.strategies.timeframe_authority import Alignment, resolve_breakout_direction_authority
from apex.structure.contracts import TrendDirection


def _frame(
    role: TimeframeRole,
    trend: TrendDirection,
    *,
    close: float = 100.0,
    low: float = 99.8,
    high: float = 100.2,
) -> TimeframeContext:
    candle = SimpleNamespace(is_closed=True, close=close, low=low, high=high)
    return cast(
        TimeframeContext,
        SimpleNamespace(
            role=role,
            structure=SimpleNamespace(trend=SimpleNamespace(direction=trend)),
            features=SimpleNamespace(atr=1.0),
            recent_candles=(candle,),
        ),
    )


def _context(*frames: TimeframeContext) -> StrategyContext:
    by_role = {frame.role: frame for frame in frames}
    return cast(
        StrategyContext,
        SimpleNamespace(frame_for_role=lambda role: by_role.get(role)),
    )


def _candidate(
    *,
    strategy: StrategyType = StrategyType.BREAKOUT_RETEST,
    direction: TradeDirection = TradeDirection.LONG,
) -> TradeCandidate:
    target = 104.0 if direction is TradeDirection.LONG else 96.0
    invalidation = 98.0 if direction is TradeDirection.LONG else 102.0
    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=strategy,
        direction=direction,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        entry=EntryZone(
            lower=99.8,
            upper=100.2,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.RETEST,
            rationale=("test retest",),
            max_chase_price=101.0 if direction is TradeDirection.LONG else 99.0,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target,
                    label="primary",
                    rationale=("test target",),
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
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
    )


def test_opposed_30m_rejects_continuation() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BEARISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH),
        ),
        _candidate(),
    )
    assert authority.routing_rejection_reason == "30m_direction_authority_opposed"


def test_opposed_15m_rejects_continuation() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BEARISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH),
        ),
        _candidate(),
    )
    assert authority.routing_rejection_reason == "15m_setup_authority_opposed"


def test_bullish_5m_retest_reclaim_is_accepted() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, close=100.2, low=99.9),
        ),
        _candidate(),
    )
    assert authority.allowed
    assert authority.retest_accepted


def test_bearish_5m_retest_rejection_is_accepted() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BEARISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BEARISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BEARISH, close=99.8, high=100.1),
        ),
        _candidate(direction=TradeDirection.SHORT),
    )
    assert authority.allowed
    assert authority.retest_accepted


def test_failed_5m_retest_rejects_continuation() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BEARISH, close=99.0, low=98.8),
        ),
        _candidate(strategy=StrategyType.BREAKOUT_CONTINUATION),
    )
    assert authority.retest_failed
    assert authority.routing_rejection_reason == "5m_retest_failed"


def test_momentum_breakout_uses_execution_alignment_not_mandatory_retest() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, close=101.0, low=100.8),
        ),
        _candidate(strategy=StrategyType.MOMENTUM_BREAKOUT),
    )
    assert authority.allowed
    assert not authority.retest_accepted
    assert authority.execution_alignment is Alignment.ALIGNED


def test_neutral_3m_refinement_survives() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, close=100.2, low=99.9),
            _frame(TimeframeRole.REFINEMENT, TrendDirection.RANGE),
        ),
        _candidate(),
    )
    assert authority.allowed
    assert not authority.conditional_only


def test_strongly_opposed_3m_is_conditional_not_rejected() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, close=100.2, low=99.9),
            _frame(TimeframeRole.REFINEMENT, TrendDirection.STRONG_BEARISH),
        ),
        _candidate(),
    )
    assert authority.allowed
    assert authority.refinement_opposed
    assert authority.conditional_only


def test_1m_timing_frame_does_not_change_direction_authority() -> None:
    authority = resolve_breakout_direction_authority(
        _context(
            _frame(TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH, close=100.2, low=99.9),
            _frame(TimeframeRole.TIMING, TrendDirection.STRONG_BEARISH),
        ),
        _candidate(),
    )
    assert authority.allowed
    assert authority.direction_authority is Alignment.ALIGNED
    assert authority.metadata()["timing_frame_used_for_direction"] is False
