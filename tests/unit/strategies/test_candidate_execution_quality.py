from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.candidate_execution_quality import (
    attach_candidate_execution_quality,
    evaluate_candidate_execution_quality,
)
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
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
from apex.structure.contracts import (
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)

NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _context(
    *,
    spread: float | None = 0.04,
    confidence: float = 1.0,
    stale: bool = False,
    active: bool = False,
) -> StrategyContext:
    structure = StructureAnalysisResult(
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH,
            strength=0.8,
            evidence=TrendEvidence(
                higher_highs=2,
                higher_lows=2,
                persistence=0.8,
                notes=("test trend",),
            ),
        ),
        levels=(),
        breaks=(),
        swings=(),
    )
    liquidity = LiquidityAnalysisResult(
        zones=(),
        sweeps=(),
        traps=(),
    )
    return StrategyContext(
        symbol="TESTUSDT",
        frames=(
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=100.0,
                features=FeatureSnapshot(atr=2.0),
                structure=structure,
                liquidity=liquidity,
                spread_percentage=spread,
                data_confidence=confidence,
                is_stale=stale,
                active_candle=active,
            ),
        ),
    )


def _candidate(
    *,
    current: float = 100.0,
    lower: float = 99.8,
    upper: float = 100.2,
    preferred: float = 100.0,
    invalidation: float = 98.0,
    max_chase: float | None = 100.5,
    confirmed: bool = True,
    provisional: bool = False,
    continuation_state: str = "fresh_break",
) -> TradeCandidate:
    entry = EntryZone(
        lower=lower,
        upper=upper,
        preferred=preferred,
        current_price=current,
        distance_from_current=abs(preferred - current),
        atr_distance=abs(preferred - current) / 2.0,
        estimated_move_missed=0.0,
        location_quality=0.9,
        mode=EntryMode.MOMENTUM_CONTINUATION,
        rationale=("test entry",),
        max_chase_price=max_chase,
    )
    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
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
            ),
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.8,
            volume_quality=0.7,
            liquidity_quality=0.7,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={
            "entry_confirmation_complete": confirmed,
            "continuation_state": continuation_state,
        },
        provisional=provisional,
    )


def test_clean_confirmed_candidate_receives_high_execution_quality() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(),
        context=_context(),
    )

    assert evaluated.constraints.trigger_complete is True
    assert evaluated.constraints.inside_entry_zone is True
    assert evaluated.result.applied_cap == pytest.approx(1.0)
    assert evaluated.result.final_score > 0.85


def test_incomplete_trigger_is_capped_even_with_good_geometry() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(confirmed=False),
        context=_context(),
    )

    assert evaluated.inputs.location == pytest.approx(0.9)
    assert evaluated.result.uncapped_score > 0.70
    assert evaluated.result.applied_cap == pytest.approx(0.55)
    assert evaluated.result.final_score == pytest.approx(0.55)


def test_missing_spread_is_neutral_input_but_not_clean_execution() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(),
        context=_context(spread=None),
    )

    assert evaluated.inputs.spread_slippage == pytest.approx(0.5)
    assert evaluated.constraints.spread_slippage_available is False
    assert evaluated.result.applied_cap == pytest.approx(0.75)


def test_chase_violation_receives_strict_cap() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(current=101.0),
        context=_context(),
    )

    assert evaluated.constraints.chase_limit_violated is True
    assert evaluated.result.applied_cap == pytest.approx(0.20)


def test_stale_data_overrides_otherwise_clean_candidate() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(),
        context=_context(stale=True),
    )

    assert evaluated.result.applied_cap == pytest.approx(0.25)


def test_mature_continuation_reduces_freshness_and_requires_trigger_cap() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(
            confirmed=False,
            continuation_state="mature_continuation",
        ),
        context=_context(),
    )

    assert evaluated.inputs.freshness == pytest.approx(0.45)
    assert evaluated.result.applied_cap == pytest.approx(0.55)


def test_infeasible_stop_geometry_forces_zero() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(invalidation=90.0),
        context=_context(),
    )

    assert evaluated.constraints.stop_feasible is False
    assert evaluated.result.final_score == pytest.approx(0.0)


def test_provisional_context_caps_candidate_even_if_candidate_flag_is_false() -> None:
    evaluated = evaluate_candidate_execution_quality(
        candidate=_candidate(),
        context=_context(active=True),
    )

    assert evaluated.constraints.provisional_evidence is True
    assert evaluated.result.applied_cap == pytest.approx(0.65)


def test_attachment_writes_final_execution_quality_to_score_dimensions() -> None:
    candidate = _candidate()

    attached = attach_candidate_execution_quality(
        candidate=candidate,
        context=_context(),
    )

    assert attached is not candidate
    assert attached.score_dimensions.execution_quality is not None
    assert attached.score_dimensions.execution_quality > 85.0
    assert candidate.score_dimensions.execution_quality is None


def test_attachment_preserves_existing_score_dimensions() -> None:
    base = _candidate()
    candidate = replace(
        base,
        score_dimensions=replace(
            base.score_dimensions,
            setup_quality=91.0,
            reward_quality=84.0,
            overall_trade_quality=88.0,
        ),
    )

    attached = attach_candidate_execution_quality(
        candidate=candidate,
        context=_context(),
    )

    assert attached.score_dimensions.setup_quality == pytest.approx(91.0)
    assert attached.score_dimensions.reward_quality == pytest.approx(84.0)
    assert attached.score_dimensions.overall_trade_quality == pytest.approx(88.0)
    assert attached.score_dimensions.execution_quality is not None


def test_setup_quality_does_not_override_capped_execution_quality() -> None:
    base = _candidate(confirmed=False)
    candidate = replace(
        base,
        score_dimensions=replace(
            base.score_dimensions,
            setup_quality=99.0,
        ),
    )

    attached = attach_candidate_execution_quality(
        candidate=candidate,
        context=_context(),
    )

    assert attached.score_dimensions.setup_quality == pytest.approx(99.0)
    assert attached.score_dimensions.execution_quality == pytest.approx(55.0)


def test_attachment_exposes_raw_cap_and_final_metadata_truthfully() -> None:
    attached = attach_candidate_execution_quality(
        candidate=_candidate(confirmed=False),
        context=_context(),
    )

    assert attached.metadata["execution_quality_uncapped"] > 70.0
    assert attached.metadata["execution_quality_cap"] == pytest.approx(55.0)
    assert attached.metadata["execution_quality_final"] == pytest.approx(55.0)
    assert attached.metadata["execution_quality_capped"] is True
    assert (
        attached.metadata["execution_quality_cap_reasons"]
        == "entry trigger or confirmation is incomplete"
    )


def test_uncapped_candidate_metadata_reports_no_fake_cap_reason() -> None:
    attached = attach_candidate_execution_quality(
        candidate=_candidate(),
        context=_context(),
    )

    assert attached.metadata["execution_quality_cap"] == pytest.approx(100.0)
    assert attached.metadata["execution_quality_capped"] is False
    assert attached.metadata["execution_quality_cap_reasons"] == ""
