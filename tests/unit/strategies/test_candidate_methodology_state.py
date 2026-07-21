from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from apex.application.methodology_strategy_layer_requirements import (
    strategy_layer_requirements,
)
from apex.domain.methodology_contracts import (
    ContextState,
    ExecutionState,
    LayeredStateSnapshot,
    RelationshipSeverity,
    RiskCondition,
    SetupState,
    StructuralBias,
    TimeframeRelationship,
)
from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.strategies.candidate_methodology_state import attach_candidate_methodology_state
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
from apex.strategies.orchestration import analyze_strategies
from apex.strategies.strategy_types import StrategyType
from apex.structure.contracts import (
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)
from apex.structure.regime import MarketRegime

NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _context(*, stale: bool = False) -> StrategyContext:
    structure = StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
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
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
                spread_percentage=0.04,
                is_stale=stale,
            ),
        ),
    )


def _candidate(
    *,
    layered_state: LayeredStateSnapshot | None = None,
) -> TradeCandidate:
    resolved_layered_state = LayeredStateSnapshot() if layered_state is None else layered_state
    return TradeCandidate(
        symbol="TESTUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
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
            location_quality=0.9,
            mode=EntryMode.MOMENTUM_CONTINUATION,
            rationale=("test entry",),
            max_chase_price=100.5,
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
            entry_quality=0.9,
            momentum_quality=0.8,
            volume_quality=0.7,
            liquidity_quality=0.7,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={"entry_confirmation_complete": True},
        layered_state=resolved_layered_state,
    )


def test_breakout_candidate_receives_measurable_layered_state() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context(),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched.layered_state.execution_state is ExecutionState.EXPANDING
    assert enriched.layered_state.setup_state is SetupState.BREAKOUT
    assert enriched.layered_state.context_state is ContextState.TRENDING_UP
    assert enriched.layered_state.structural_bias is StructuralBias.BULLISH
    assert enriched.layered_state.risk_condition is RiskCondition.NORMAL


def test_existing_explicit_layered_state_is_preserved() -> None:
    explicit = LayeredStateSnapshot(
        execution_state=ExecutionState.CLEAN,
        setup_state=SetupState.RANGE,
        context_state=ContextState.RANGE_BOUND,
        structural_bias=StructuralBias.NEUTRAL,
        risk_condition=RiskCondition.NORMAL,
    )
    candidate = _candidate(layered_state=explicit)

    enriched = attach_candidate_methodology_state(
        candidate=candidate,
        context=_context(),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched is candidate
    assert enriched.layered_state is explicit


def test_stale_data_sets_chaotic_execution_and_stale_risk() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context(stale=True),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched.layered_state.execution_state is ExecutionState.CHAOTIC
    assert enriched.layered_state.risk_condition is RiskCondition.STALE_DATA


def test_orchestration_populates_layered_state(monkeypatch) -> None:
    candidate = _candidate()

    def generator(
        context: StrategyContext,
        *,
        decision_time: datetime,
    ) -> tuple[TradeCandidate, ...]:
        del context
        return (replace(candidate, decision_time=decision_time),)

    monkeypatch.setattr(
        "apex.strategies.orchestration.STRATEGY_REGISTRY",
        ((StrategyType.MOMENTUM_BREAKOUT, generator),),
    )

    result = analyze_strategies(_context(), decision_time=NOW)

    assert len(result.candidates) == 1
    assert result.candidates[0].layered_state != LayeredStateSnapshot()
    assert result.candidates[0].layered_state.setup_state is SetupState.BREAKOUT


def _context_with_macro(direction: TrendDirection) -> StrategyContext:
    macro_structure = StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=direction,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
    )
    entry_structure = StructureAnalysisResult(
        swings=(),
        trend=TrendAnalysis(
            direction=TrendDirection.BULLISH,
            strength=0.8,
            evidence=TrendEvidence(persistence=0.8),
        ),
    )
    return StrategyContext(
        symbol="TESTUSDT",
        frames=(
            TimeframeContext(
                timeframe="4h",
                role=TimeframeRole.MACRO,
                current_price=100.0,
                features=FeatureSnapshot(atr=4.0),
                structure=macro_structure,
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
            ),
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=100.0,
                features=FeatureSnapshot(atr=2.0),
                structure=entry_structure,
                liquidity=LiquidityAnalysisResult(zones=(), sweeps=(), traps=()),
                spread_percentage=0.04,
            ),
        ),
    )


def test_structured_range_uses_compatible_mixed_execution_state() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context(),
        regime=MarketRegime.STABLE_RANGE,
    )

    assert enriched.layered_state.execution_state is ExecutionState.MIXED


def test_every_strategy_mapping_matches_declared_layer_requirements() -> None:
    for strategy in StrategyType:
        candidate = replace(_candidate(), strategy=strategy)
        enriched = attach_candidate_methodology_state(
            candidate=candidate,
            context=_context(),
            regime=MarketRegime.WEAK_UPTREND,
        )
        requirements = strategy_layer_requirements(strategy)

        assert enriched.layered_state.execution_state in requirements.execution_states
        assert enriched.layered_state.setup_state in requirements.setup_states


def test_aligned_macro_structure_populates_with_trend_relationship() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context_with_macro(TrendDirection.BULLISH),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched.layered_state.timeframe_relationship is TimeframeRelationship.WITH_TREND
    assert enriched.layered_state.relationship_severity is RelationshipSeverity.NONE


def test_weak_opposing_macro_structure_populates_mild_mixed_relationship() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context_with_macro(TrendDirection.BEARISH),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched.layered_state.timeframe_relationship is TimeframeRelationship.MIXED
    assert enriched.layered_state.relationship_severity is RelationshipSeverity.MILD


def test_missing_higher_timeframe_preserves_unavailable_relationship() -> None:
    enriched = attach_candidate_methodology_state(
        candidate=_candidate(),
        context=_context(),
        regime=MarketRegime.WEAK_UPTREND,
    )

    assert enriched.layered_state.timeframe_relationship is TimeframeRelationship.UNAVAILABLE
    assert enriched.layered_state.relationship_severity is RelationshipSeverity.UNAVAILABLE
