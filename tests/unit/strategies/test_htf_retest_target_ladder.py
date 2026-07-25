from __future__ import annotations

from datetime import UTC, datetime

import apex.strategies.htf_retest_fallback as fallback_module
from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import (
    EntryMode,
    EntryOpportunityHorizon,
    EntryZone,
    InvalidationType,
    TargetLevel,
    TargetType,
    TradeDirection,
)
from apex.structure.contracts import (
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)


def _frame(timeframe: str, role: TimeframeRole) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=100.0,
        features=FeatureSnapshot(
            atr=1.0,
            rsi_slope=-1.0,
            macd_histogram=-1.0,
            rate_of_change=-1.0,
        ),
        structure=StructureAnalysisResult(
            swings=(),
            trend=TrendAnalysis(
                direction=TrendDirection.BULLISH,
                strength=0.8,
                evidence=TrendEvidence(),
            ),
        ),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        exchange_tick_size=0.01,
    )


def test_htf_fallback_publishes_full_structural_target_ladder(monkeypatch) -> None:
    context = StrategyContext(
        symbol="TEST/USDT",
        frames=(
            _frame("15m", TimeframeRole.INTRADAY),
            _frame("5m", TimeframeRole.SETUP),
            _frame("3m", TimeframeRole.ENTRY),
        ),
    )
    targets = (
        TargetLevel(
            kind=TargetType.STRUCTURAL,
            price=102.0,
            label="tp1",
            rationale=("front-run of 3m opposing resistance zone",),
        ),
        TargetLevel(
            kind=TargetType.STRUCTURAL,
            price=104.0,
            label="tp2",
            rationale=("front-run of 5m opposing resistance zone",),
        ),
        TargetLevel(
            kind=TargetType.STRUCTURAL,
            price=108.0,
            label="tp3",
            rationale=("front-run of 15m opposing resistance zone",),
        ),
    )
    entry = EntryZone(
        lower=99.8,
        upper=100.0,
        preferred=99.9,
        current_price=100.0,
        distance_from_current=0.1,
        atr_distance=0.1,
        estimated_move_missed=0.0,
        location_quality=0.8,
        mode=EntryMode.SCALED_ENTRY,
        rationale=("test structural retest",),
        horizon=EntryOpportunityHorizon.NEARBY,
        max_chase_price=100.2,
    )

    monkeypatch.setattr(
        fallback_module,
        "generate_trend_pullback_candidates",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        fallback_module,
        "build_structural_target_ladder",
        lambda *args, **kwargs: targets,
    )
    monkeypatch.setattr(
        fallback_module,
        "_invalidation_geometry",
        lambda *args, **kwargs: (98.5, InvalidationType.STRUCTURAL),
    )
    monkeypatch.setattr(
        fallback_module,
        "_entry_references",
        lambda *args, **kwargs: (object(),),
    )
    monkeypatch.setattr(
        fallback_module,
        "find_entry_zones",
        lambda *args, **kwargs: (entry,),
    )
    monkeypatch.setattr(
        fallback_module,
        "_selected_entry_geometry_metadata",
        lambda *args, **kwargs: {},
    )

    generated = fallback_module.generate_htf_aware_trend_pullback_candidates(
        context,
        decision_time=datetime(2026, 7, 25, tzinfo=UTC),
    )

    assert len(generated) == 1
    candidate = generated[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.targets.levels == targets
    assert candidate.metadata["target_ladder_count"] == 3
    assert candidate.metadata["target_1_price"] == 102.0
    assert candidate.metadata["target_2_price"] == 104.0
    assert candidate.metadata["target_3_price"] == 108.0
