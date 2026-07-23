"""Verify the shared registry boundary applies breakout routing."""

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
from apex.strategies.registry import (
    run_strategy_generator,
    run_strategy_generator_with_diagnostics,
)
from apex.strategies.strategy_types import StrategyType
from apex.structure.contracts import TrendDirection

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _frame(role: TimeframeRole, trend: TrendDirection) -> TimeframeContext:
    candle = SimpleNamespace(is_closed=True, close=100.1, low=99.9, high=100.2)
    return cast(
        TimeframeContext,
        SimpleNamespace(
            role=role,
            structure=SimpleNamespace(trend=SimpleNamespace(direction=trend)),
            features=SimpleNamespace(atr=1.0),
            recent_candles=(candle,),
        ),
    )


def _context() -> StrategyContext:
    frames = {
        TimeframeRole.INTRADAY: _frame(TimeframeRole.INTRADAY, TrendDirection.BEARISH),
        TimeframeRole.SETUP: _frame(TimeframeRole.SETUP, TrendDirection.BULLISH),
        TimeframeRole.ENTRY: _frame(TimeframeRole.ENTRY, TrendDirection.BULLISH),
    }
    return cast(
        StrategyContext,
        SimpleNamespace(frame_for_role=lambda role: frames.get(role)),
    )


def _candidate() -> TradeCandidate:
    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.BREAKOUT_RETEST,
        direction=TradeDirection.LONG,
        decision_time=NOW,
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
            max_chase_price=101.0,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=104.0,
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
        metadata={},
    )


def _generator(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    del context, decision_time
    return (_candidate(),)


def test_registry_boundary_rejects_breakout_opposed_by_30m_authority() -> None:
    assert run_strategy_generator(_generator, _context(), decision_time=NOW) == ()


def test_registry_boundary_preserves_breakout_rejection_diagnostics() -> None:
    result = run_strategy_generator_with_diagnostics(
        _generator,
        _context(),
        decision_time=NOW,
    )

    assert result.candidates == ()
    assert result.raw_breakout_candidate_count == 1
    assert result.conditional_candidate_count == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason_code == "30m_direction_authority_opposed"
    assert result.rejected[0].candidate.metadata["direction_authority"] == "opposed"
    assert result.rejected[0].candidate.metadata["timing_frame_used_for_direction"] is False
