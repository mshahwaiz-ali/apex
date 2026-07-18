from datetime import UTC, datetime, timedelta

import pytest

from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyAnalysisResult,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _candidate(
    *,
    symbol: str = "BTC/USDT",
    decision_time: datetime = NOW,
    strategy: StrategyType = StrategyType.TREND_PULLBACK,
) -> TradeCandidate:
    return TradeCandidate(
        symbol=symbol,
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=decision_time,
        entry=EntryZone(
            lower=99.0,
            upper=100.0,
            preferred=99.5,
            current_price=100.0,
            distance_from_current=0.005,
            atr_distance=0.25,
            estimated_move_missed=0.005,
            location_quality=0.8,
            mode=EntryMode.PULLBACK,
            rationale=("nearby pullback",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=97.0,
            rationale=("structure fails",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=106.0,
                    label="primary",
                    rationale=("opposing structure",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.7,
            volume_quality=0.5,
            liquidity_quality=0.5,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("valid thesis",)),
        metadata={},
    )


def test_rejects_empty_evaluated_strategy_list() -> None:
    with pytest.raises(ValueError, match="at least one evaluated strategy"):
        StrategyAnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            candidates=(),
            evaluated_strategies=(),
        )


def test_rejects_duplicate_evaluated_strategies() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        StrategyAnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            candidates=(),
            evaluated_strategies=(
                StrategyType.TREND_PULLBACK,
                StrategyType.TREND_PULLBACK,
            ),
        )


def test_rejects_candidate_with_mismatched_symbol() -> None:
    with pytest.raises(ValueError, match="candidate symbol"):
        StrategyAnalysisResult(
            symbol="ETH/USDT",
            decision_time=NOW,
            candidates=(_candidate(),),
            evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        )


def test_rejects_candidate_with_mismatched_decision_time() -> None:
    with pytest.raises(ValueError, match="candidate decision time"):
        StrategyAnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW + timedelta(minutes=5),
            candidates=(_candidate(),),
            evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        )


def test_rejects_candidate_from_unevaluated_strategy() -> None:
    with pytest.raises(ValueError, match="candidate strategy"):
        StrategyAnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            candidates=(_candidate(strategy=StrategyType.MOMENTUM_BREAKOUT),),
            evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        )


def test_rejects_candidate_order_that_differs_from_registry_order() -> None:
    with pytest.raises(ValueError, match="stable registry ordering"):
        StrategyAnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            candidates=(
                _candidate(strategy=StrategyType.TREND_PULLBACK),
                _candidate(strategy=StrategyType.MOMENTUM_BREAKOUT),
            ),
            evaluated_strategies=(
                StrategyType.MOMENTUM_BREAKOUT,
                StrategyType.TREND_PULLBACK,
            ),
        )


def test_accepts_multiple_candidates_from_same_strategy_in_stable_position() -> None:
    result = StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(
            _candidate(strategy=StrategyType.MOMENTUM_BREAKOUT),
            _candidate(strategy=StrategyType.TREND_PULLBACK),
            _candidate(strategy=StrategyType.TREND_PULLBACK),
        ),
        evaluated_strategies=(
            StrategyType.MOMENTUM_BREAKOUT,
            StrategyType.TREND_PULLBACK,
        ),
    )

    assert len(result.candidates) == 3
