from datetime import UTC, datetime

import pytest

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    EntryMode,
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    TradeDirection,
    generate_trend_pullback_candidates,
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
    trend = TrendDirection.BULLISH if bullish else TrendDirection.BEARISH
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
            representative_price=99.0 if bullish else 101.0,
            low=98.9 if bullish else 100.9,
            high=99.1 if bullish else 101.1,
            role=LevelRole.SUPPORT if bullish else LevelRole.RESISTANCE,
            status=LevelStatus.ACTIVE,
            touches=1,
            pivot_indices=(2,),
            last_touch_index=2,
        ),
        StructureLevel(
            representative_price=106.0,
            low=105.9,
            high=106.1,
            role=LevelRole.RESISTANCE,
            status=LevelStatus.ACTIVE,
            touches=1,
            pivot_indices=(3,),
            last_touch_index=3,
        ),
    )
    return StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=trend,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
        levels=tuple(
            sorted(
                levels,
                key=lambda item: (
                    item.representative_price,
                    item.role.value,
                    item.last_touch_index,
                ),
            )
        ),
    )


def _frame(
    *,
    bullish: bool,
    role: TimeframeRole,
    active: bool = False,
    sparse_features: bool = False,
) -> TimeframeContext:
    features = (
        FeatureSnapshot(atr=2.0, ema_fast=99.5 if bullish else 100.5)
        if sparse_features
        else FeatureSnapshot(
            atr=2.0,
            ema_fast=99.5 if bullish else 100.5,
            ema_slow=98.5 if bullish else 101.5,
            vwap=99.2 if bullish else 100.8,
            rsi=52.0 if bullish else 48.0,
            rsi_slope=0.4 if bullish else -0.4,
            macd_histogram=0.2 if bullish else -0.2,
            rate_of_change=0.3 if bullish else -0.3,
            relative_volume=1.2,
        )
    )
    return TimeframeContext(
        timeframe="4h" if role is TimeframeRole.MACRO else "5m",
        role=role,
        current_price=100.0,
        features=features,
        structure=_structure(bullish=bullish),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        active_candle=active,
    )


def _context(
    *,
    bullish: bool,
    contradiction: bool = False,
    active: bool = False,
    sparse_features: bool = False,
) -> StrategyContext:
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            _frame(bullish=not bullish if contradiction else bullish, role=TimeframeRole.MACRO),
            _frame(
                bullish=bullish,
                role=TimeframeRole.ENTRY,
                active=active,
                sparse_features=sparse_features,
            ),
        ),
    )


def test_generates_long_trend_pullback_near_current_price() -> None:
    candidates = generate_trend_pullback_candidates(
        _context(bullish=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.LONG
    assert candidate.entry.mode is EntryMode.SCALED_ENTRY
    assert candidate.entry.preferred == 99.0
    assert candidate.entry.lower == 98.9
    assert candidate.entry.upper == 99.1
    assert candidate.metadata["entry_geometry_owner"] == "strategy_structure_level"
    assert candidate.metadata["retest_zone_low"] == 98.9
    assert candidate.metadata["retest_zone_high"] == 99.1
    assert candidate.metadata["retest_trigger_level"] == 99.0
    assert candidate.metadata["retest_penetration_allowance"] == pytest.approx(0.2)
    assert candidate.metadata["breakout_level_available"] is False
    assert candidate.invalidation.price < candidate.entry.lower
    assert candidate.targets.levels[0].price > candidate.entry.upper


def test_generates_short_trend_pullback_near_current_price() -> None:
    candidates = generate_trend_pullback_candidates(
        _context(bullish=False),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.direction is TradeDirection.SHORT
    assert candidate.entry.mode is EntryMode.SCALED_ENTRY
    assert candidate.entry.preferred == 101.0
    assert candidate.entry.lower == 100.9
    assert candidate.entry.upper == 101.1
    assert candidate.metadata["entry_geometry_owner"] == "strategy_structure_level"
    assert candidate.metadata["retest_zone_low"] == 100.9
    assert candidate.metadata["retest_zone_high"] == 101.1
    assert candidate.metadata["retest_trigger_level"] == 101.0
    assert candidate.metadata["retest_confirmation_rule"] == ("hold_or_reject_below_retest_zone")
    assert candidate.invalidation.price > candidate.entry.upper
    assert candidate.targets.levels[0].price < candidate.entry.lower


def test_marks_strong_higher_timeframe_contradiction() -> None:
    candidates = generate_trend_pullback_candidates(
        _context(bullish=True, contradiction=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].metadata["higher_timeframe_conflict"] is True
    assert candidates[0].quality.conflict_penalty > 0.0


def test_allows_missing_optional_indicators() -> None:
    candidates = generate_trend_pullback_candidates(
        _context(bullish=True, sparse_features=True),
        decision_time=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].quality.momentum_quality == 0.5


def test_marks_active_candle_candidate_provisional() -> None:
    candidates = generate_trend_pullback_candidates(
        _context(bullish=True, active=True),
        decision_time=NOW,
    )

    assert candidates[0].provisional is True
    assert "active-candle evidence is provisional" in candidates[0].evidence.warnings


def test_output_is_deterministic() -> None:
    context = _context(bullish=True)

    first = generate_trend_pullback_candidates(context, decision_time=NOW)
    second = generate_trend_pullback_candidates(context, decision_time=NOW)

    assert first == second
