from dataclasses import FrozenInstanceError

import pytest

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.structure.contracts import (
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)


def _structure() -> StructureAnalysisResult:
    return StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.UNCERTAIN,
            strength=0.2,
            evidence=TrendEvidence(persistence=0.2),
        ),
    )


def _frame(*, timeframe: str, role: TimeframeRole) -> TimeframeContext:
    return TimeframeContext(
        timeframe=timeframe,
        role=role,
        current_price=100.0,
        features=FeatureSnapshot(atr=2.0),
        structure=_structure(),
        liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
    )


def test_timing_only_frame_cannot_establish_thesis() -> None:
    with pytest.raises(ValueError, match="timing-only"):
        StrategyContext(
            symbol="BTC/USDT",
            frames=(_frame(timeframe="1m", role=TimeframeRole.TIMING),),
        )


def test_refinement_only_frame_cannot_establish_thesis() -> None:
    with pytest.raises(ValueError, match="timing-only"):
        StrategyContext(
            symbol="BTC/USDT",
            frames=(_frame(timeframe="3m", role=TimeframeRole.REFINEMENT),),
        )


def test_frames_must_follow_stable_high_to_low_role_order() -> None:
    with pytest.raises(ValueError, match="stable highest-to-lowest"):
        StrategyContext(
            symbol="BTC/USDT",
            frames=(
                _frame(timeframe="5m", role=TimeframeRole.ENTRY),
                _frame(timeframe="4h", role=TimeframeRole.MACRO),
            ),
        )


def test_timeframe_names_must_be_unique() -> None:
    with pytest.raises(ValueError, match="timeframe names must be unique"):
        StrategyContext(
            symbol="BTC/USDT",
            frames=(
                _frame(timeframe="5m", role=TimeframeRole.SETUP),
                _frame(timeframe="5m", role=TimeframeRole.ENTRY),
            ),
        )


def test_timeframe_roles_must_be_unique() -> None:
    with pytest.raises(ValueError, match="timeframe roles must be unique"):
        StrategyContext(
            symbol="BTC/USDT",
            frames=(
                _frame(timeframe="5m", role=TimeframeRole.ENTRY),
                _frame(timeframe="3m", role=TimeframeRole.ENTRY),
            ),
        )


def test_entry_frame_is_selected_ahead_of_timing_frame() -> None:
    entry = _frame(timeframe="5m", role=TimeframeRole.ENTRY)
    timing = _frame(timeframe="1m", role=TimeframeRole.TIMING)
    context = StrategyContext(symbol="BTC/USDT", frames=(entry, timing))

    assert context.decision_frame is entry
    assert context.current_price == entry.current_price
    assert context.atr == entry.features.atr


def test_context_and_nested_frames_are_frozen() -> None:
    frame = _frame(timeframe="5m", role=TimeframeRole.ENTRY)
    context = StrategyContext(symbol="BTC/USDT", frames=(frame,))

    with pytest.raises(FrozenInstanceError):
        context.symbol = "ETH/USDT"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        frame.current_price = 101.0  # type: ignore[misc]


def test_repeated_context_construction_is_deterministic() -> None:
    first = StrategyContext(
        symbol="BTC/USDT",
        frames=(_frame(timeframe="5m", role=TimeframeRole.ENTRY),),
    )
    second = StrategyContext(
        symbol="BTC/USDT",
        frames=(_frame(timeframe="5m", role=TimeframeRole.ENTRY),),
    )

    assert first == second


def test_frame_rejects_invalid_price_metadata() -> None:
    with pytest.raises(ValueError, match="analysis price"):
        TimeframeContext(
            timeframe="5m",
            role=TimeframeRole.ENTRY,
            current_price=100.0,
            latest_closed_price=100.0,
            analysis_price=0.0,
            features=FeatureSnapshot(atr=2.0),
            structure=_structure(),
            liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        )


def test_frame_rejects_invalid_staleness_metadata() -> None:
    with pytest.raises(ValueError, match="staleness seconds"):
        TimeframeContext(
            timeframe="5m",
            role=TimeframeRole.ENTRY,
            current_price=100.0,
            staleness_seconds=-1.0,
            features=FeatureSnapshot(atr=2.0),
            structure=_structure(),
            liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
        )
