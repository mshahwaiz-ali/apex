"""Tests for the Step 8 strategy-applicability matrix."""

from apex.strategies import (
    StrategyApplicabilityState,
    StrategyType,
    build_strategy_applicability,
)
from apex.structure.regime import MarketRegime

ALL_STRATEGIES = tuple(StrategyType)


def test_trend_regime_marks_continuation_strategies_applicable() -> None:
    eligible = (
        StrategyType.TREND_PULLBACK,
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
    )

    matrix = build_strategy_applicability(
        regime=MarketRegime.STRONG_UPTREND,
        evaluated=ALL_STRATEGIES,
        eligible=eligible,
        higher_timeframe_breakout=False,
    )

    assert set(matrix) == set(ALL_STRATEGIES)
    assert matrix[StrategyType.TREND_PULLBACK].state is StrategyApplicabilityState.APPLICABLE
    assert matrix[StrategyType.RANGE_REVERSAL].state is StrategyApplicabilityState.CONDITIONAL


def test_higher_timeframe_breakout_creates_conditional_applicability() -> None:
    eligible = (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_BREAKOUT,
    )

    matrix = build_strategy_applicability(
        regime=MarketRegime.UNCERTAIN,
        evaluated=ALL_STRATEGIES,
        eligible=eligible,
        higher_timeframe_breakout=True,
    )

    assert (
        matrix[StrategyType.BREAKOUT_CONTINUATION].state is StrategyApplicabilityState.CONDITIONAL
    )
    assert matrix[StrategyType.MOMENTUM_BREAKOUT].state is StrategyApplicabilityState.CONDITIONAL
    assert matrix[StrategyType.TREND_PULLBACK].state is StrategyApplicabilityState.CONDITIONAL


def test_applicability_scores_are_normalized() -> None:
    matrix = build_strategy_applicability(
        regime=MarketRegime.STABLE_RANGE,
        evaluated=ALL_STRATEGIES,
        eligible=(
            StrategyType.LIQUIDITY_REJECTION_REVERSAL,
            StrategyType.RANGE_REVERSAL,
        ),
        higher_timeframe_breakout=False,
    )

    assert all(0.0 <= record.score <= 100.0 for record in matrix.values())
    assert matrix[StrategyType.RANGE_REVERSAL].score == 100.0
    assert matrix[StrategyType.TREND_PULLBACK].score == 55.0
