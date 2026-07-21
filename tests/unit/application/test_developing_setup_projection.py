from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_analysis import serialize_symbol_analysis
from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.discovery_setup import build_discovery_assessment
from apex.application.public_output import serialize_symbol_analysis as serialize_public_analysis
from apex.presentation.discovery_output import (
    render_discovery_analysis,
    render_discovery_scan,
)
from apex.presentation.scan_groups import ScanGroup, classify_scan_result
from apex.scoring.contracts import (
    CandidateOutcome,
    CandidateSelectionResult,
    ConflictSummary,
    DirectionalConsensus,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
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

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _ranked_pending_candidate() -> RankedCandidate:
    candidate = TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=100.0,
            preferred=99.5,
            current_price=101.0,
            distance_from_current=1.0,
            atr_distance=0.5,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=EntryMode.PULLBACK,
            rationale=("wait for the structural pullback",),
            max_chase_price=100.5,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=97.0,
            rationale=("pullback structure fails below support",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=104.0,
                    label="TP1",
                    rationale=("prior structural high",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.6,
            momentum_quality=0.7,
            volume_quality=0.7,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("trend structure remains valid",)),
        metadata={},
    )
    scored = ScoredCandidate(
        candidate_id="pending-1",
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points={"quality": 72.0},
            penalty_points={},
            base_score=72.0,
            total_penalty=0.0,
            final_score=72.0,
        ),
        normalized_metrics={},
    )
    return RankedCandidate(
        scored=scored,
        rank=1,
        outcome=CandidateOutcome.ACCEPTED,
        reasons=(),
        tie_break=("pending-1",),
    )


def _selection() -> CandidateSelectionResult:
    ranked = _ranked_pending_candidate()
    conflict = ConflictSummary(
        directional_consensus=DirectionalConsensus.LONG,
        long_count=1,
        short_count=0,
        duplicate_groups=(),
        warnings=(),
    )
    return CandidateSelectionResult(
        symbol="BTCUSDT",
        decision_time=NOW,
        all_scored_candidates=(ranked.scored,),
        ranked_candidates=(ranked,),
        rejected_candidates=(),
        conflict_summary=conflict,
        directional_consensus=DirectionalConsensus.LONG,
        selected_candidate=None,
        no_trade_reason="valid setups exist, but none has a currently executable entry",
        evaluated_strategy_order=(StrategyType.TREND_PULLBACK,),
        configuration_id="test",
        metadata={},
    )


def _analysis() -> SymbolAnalysis:
    return SymbolAnalysis(
        symbol="BTCUSDT",
        generated_at=NOW,
        assessment=build_discovery_assessment(_selection()),
        candidate_count=1,
        evaluated_timeframes=("15m",),
        regime_by_timeframe={"15m": "trending_up"},
        data_quality_by_timeframe={},
    )


def test_non_executable_valid_candidate_is_preserved_without_selecting_trade() -> None:
    assessment = build_discovery_assessment(_selection())

    assert assessment.setup is None
    assert assessment.developing_setup is not None
    assert assessment.developing_setup.candidate_id == "pending-1"
    assert assessment.developing_setup.execution_allowed_now is False


def test_developing_setup_serializes_full_geometry() -> None:
    payload = serialize_symbol_analysis(_analysis())
    developing = payload["developing_setup"]

    assert payload["setup"] is None
    assert developing is not None
    assert developing["entry"]["preferred"] == 99.5
    assert developing["stop_loss"]["price"] < 99.0
    targets = developing["take_profits"]
    assert [target["price"] for target in targets] == [104.0]
    assert targets[0]["target_type"] == "structural"


def test_public_output_groups_pending_setup_as_developing() -> None:
    payload = serialize_public_analysis(_analysis())

    assert payload["result_group"] == "developing"
    assert payload["setup"] is None
    assert payload["developing_setup"] is not None
    assert classify_scan_result(payload) is ScanGroup.CONDITIONAL


def test_pending_analysis_omits_unavailable_selected_semantics() -> None:
    text = render_discovery_analysis(serialize_public_analysis(_analysis()))

    assert "Decision" in text
    assert "Trade plan" in text
    assert "no canonical entry opportunity exists" not in text
    assert "no canonical target candidates are available" not in text


def test_scan_uses_compact_pending_card() -> None:
    result = serialize_public_analysis(_analysis())
    text = render_discovery_scan(
        {
            "results": [result],
            "total_analysis_count": 1,
            "displayed_analysis_count": 1,
            "selected_setup_count": 0,
            "long_candidate_count": 1,
            "short_candidate_count": 0,
            "status_counts": {"PULLBACK_PREFERRED": 1},
        }
    )

    assert "Developing / Watch" not in text
    assert "Developing / follow-up" in text
    assert "Trade Management" not in text
    assert "Candlestick Evidence" not in text


def test_developing_setup_exposes_typed_conditional_plan() -> None:
    assessment = build_discovery_assessment(_selection())

    assert assessment.developing_setup is not None
    plan = assessment.developing_setup.conditional_plan
    assert plan is not None
    assert plan.trigger.level == assessment.developing_setup.entry.preferred
    assert (
        plan.pre_entry_invalidation.price
        == _selection().ranked_candidates[0].scored.candidate.invalidation.price
    )
    assert plan.pre_entry_invalidation.price != assessment.developing_setup.stop_loss.price
    assert plan.conditional_order_eligible is False
    assert plan.reason_not_executable_now
    assert plan.recommended_order_intent.value in {"limit", "alert_only", "stop"}


def test_developing_setup_serializes_conditional_plan() -> None:
    payload = serialize_symbol_analysis(_analysis())
    developing = payload["developing_setup"]

    assert developing is not None
    plan = developing["conditional_plan"]
    assert plan is not None
    assert plan["trigger"]["level"] == developing["entry"]["preferred"]
    assert (
        plan["pre_entry_invalidation"]["price"]
        == _selection().ranked_candidates[0].scored.candidate.invalidation.price
    )
    assert plan["pre_entry_invalidation"]["price"] != developing["stop_loss"]["price"]
    assert plan["conditional_order_eligible"] is False
    assert plan["reason_not_executable_now"]


def test_conditional_plan_exposes_geometry_provenance() -> None:
    assessment = build_discovery_assessment(_selection())

    assert assessment.developing_setup is not None
    plan = assessment.developing_setup.conditional_plan
    assert plan is not None
    assert plan.geometry_basis == "candidate_entry_zone"
    assert plan.trigger_matches_preferred_entry is True
    assert plan.geometry_is_trigger_relative is True
    assert plan.stop_basis == "structural_invalidation_buffered_from_candidate_entry"
    assert plan.targets_basis == "strategy_supplied_targets_with_explicit_provenance"


def test_conditional_plan_serializes_geometry_provenance() -> None:
    payload = serialize_symbol_analysis(_analysis())
    developing = payload["developing_setup"]

    assert developing is not None
    geometry = developing["conditional_plan"]["geometry"]
    assert geometry["geometry_basis"] == "candidate_entry_zone"
    assert geometry["trigger_matches_preferred_entry"] is True
    assert geometry["geometry_is_trigger_relative"] is True
