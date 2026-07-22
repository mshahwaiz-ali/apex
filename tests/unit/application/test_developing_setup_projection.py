from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.application.discovery_analysis import (
    _apply_geometry_no_trade_reason,
    serialize_symbol_analysis,
)
from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.discovery_setup import _build_setup, build_discovery_assessment
from apex.application.public_output import serialize_symbol_analysis as serialize_public_analysis
from apex.domain.methodology_contracts import ScoreDimensions
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
            max_chase_price=101.5,
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
        selected_future_candidate=None,
        no_trade_reason="valid setups exist, but none has a currently executable entry",
        evaluated_strategy_order=(StrategyType.TREND_PULLBACK,),
        configuration_id="test",
        metadata={},
    )


def test_setup_projects_authoritative_capped_quality_dimensions() -> None:
    ranked = _ranked_pending_candidate()
    candidate = replace(
        ranked.candidate,
        score_dimensions=ScoreDimensions(
            setup_quality=61.0,
            execution_quality=55.0,
            reward_quality=70.0,
            overall_trade_quality=64.0,
        ),
    )
    setup = _build_setup(replace(ranked, scored=replace(ranked.scored, candidate=candidate)))

    assert setup.quality_dimensions is not None
    assert setup.quality_dimensions.setup_quality == 61.0
    assert setup.quality_dimensions.execution_quality == 55.0
    assert setup.quality_dimensions.target_quality == 70.0
    assert setup.quality_dimensions.overall_trade_quality == 64.0


def test_public_maximum_chase_preserves_configured_minimum_net_r() -> None:
    ranked = _ranked_pending_candidate()
    wider_target = replace(
        ranked.candidate.targets,
        levels=(replace(ranked.candidate.targets.levels[0], price=106.0),),
    )
    candidate = replace(
        ranked.candidate,
        targets=wider_target,
        metadata={
            "expected_cost_pct": 0.10,
            "geometry_minimum_tp1_reward_to_risk": 1.25,
        },
    )

    setup = _build_setup(replace(ranked, scored=replace(ranked.scored, candidate=candidate)))

    chase = setup.entry.maximum_chase_price
    target = setup.take_profits[0].price
    stop = setup.stop_loss.price
    cost = chase * 0.10 / 100.0
    net_r = (target - chase - cost) / (chase - stop + cost)

    assert setup.entry.upper <= chase < ranked.candidate.entry.max_chase_price  # type: ignore[operator]
    assert net_r >= 1.25 - 1e-9


def test_primary_entry_opportunity_uses_same_post_policy_chase_boundary() -> None:
    ranked = _ranked_pending_candidate()
    candidate = replace(
        ranked.candidate,
        entry_opportunities=(ranked.candidate.entry,),
        targets=replace(
            ranked.candidate.targets,
            levels=(replace(ranked.candidate.targets.levels[0], price=106.0),),
        ),
        metadata={
            "expected_cost_pct": 0.10,
            "geometry_minimum_tp1_reward_to_risk": 1.25,
        },
    )

    setup = _build_setup(replace(ranked, scored=replace(ranked.scored, candidate=candidate)))

    assert setup.entry_opportunities[0].maximum_chase_price == pytest.approx(
        setup.entry.maximum_chase_price
    )


def test_geometry_rejection_replaces_false_no_candidates_reason() -> None:
    selection = replace(
        _selection(),
        all_scored_candidates=(),
        ranked_candidates=(),
        selected_candidate=None,
        selected_future_candidate=None,
        no_trade_reason="no strategy candidates were generated",
    )
    enforcement = type("_Enforcement", (), {"rejected_candidate_count": 3})()

    updated = _apply_geometry_no_trade_reason(selection, enforcement)  # type: ignore[arg-type]

    assert updated.no_trade_reason == (
        "all 3 generated candidates were rejected by geometry safety"
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
