from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import apex.application.methodology_candidate_routing as candidate_routing
from apex.application.methodology_candidate_routing import (
    _htf_assessment_from_layered_state,
    apply_methodology_candidate_routing,
    evaluate_methodology_candidate_routing,
    methodology_candidate_routing_payload,
)
from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
)
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_contracts import PrimaryMarketState
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.domain.methodology_contracts import (
    ContextState,
    ExecutionState,
    LayeredStateSnapshot,
    RelationshipSeverity,
    SetupState,
    TimeframeRelationship,
)
from apex.strategies.analysis import CandidateActionability, StrategyAnalysisResult
from apex.strategies.contracts import EntryMode, StrategyEvidence, TradeCandidate, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True)
class _Entry:
    mode: EntryMode


@dataclass(frozen=True)
class _Candidate:
    symbol: str
    strategy: StrategyType
    direction: TradeDirection
    decision_time: datetime
    evidence: StrategyEvidence
    entry: _Entry
    provisional: bool = False
    layered_state: LayeredStateSnapshot = field(default_factory=LayeredStateSnapshot)


def _candidate(
    strategy: StrategyType,
    *,
    entry_mode: EntryMode = EntryMode.MARKET_NEAR,
    layered_state: LayeredStateSnapshot | None = None,
) -> TradeCandidate:
    return cast(
        TradeCandidate,
        _Candidate(
            symbol="BTCUSDT",
            strategy=strategy,
            direction=TradeDirection.LONG,
            decision_time=datetime(2026, 7, 18, tzinfo=UTC),
            evidence=StrategyEvidence(
                supporting=("price structure supports the setup",),
                structure_references=("structure reference",),
                liquidity_references=("liquidity reference",),
            ),
            entry=_Entry(entry_mode),
            layered_state=(LayeredStateSnapshot() if layered_state is None else layered_state),
        ),
    )


def _analysis() -> StrategyAnalysisResult:
    trend = _candidate(StrategyType.TREND_PULLBACK)
    range_reversal = _candidate(StrategyType.RANGE_REVERSAL)
    candidates = (trend, range_reversal)
    return StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=candidates,
        evaluated_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.RANGE_REVERSAL,
        ),
        eligible_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.RANGE_REVERSAL,
        ),
        candidate_actionability=tuple(
            CandidateActionability(candidate=item, status=EntryStatus.READY_NOW)
            for item in candidates
        ),
    )


def _decision(
    strategy: StrategyType,
    action: StrategyEnforcementAction,
) -> StrategyEnforcementDecision:
    return StrategyEnforcementDecision(
        strategy=strategy,
        action=action,
        reason_codes=(f"TEST_{action.value.upper()}",),
        reasons=(f"{strategy.value} is {action.value}",),
    )


def test_shadow_mode_preserves_all_candidates() -> None:
    analysis = _analysis()

    result = apply_methodology_candidate_routing(
        analysis,
        (
            _decision(
                StrategyType.RANGE_REVERSAL,
                StrategyEnforcementAction.SUPPRESS,
            ),
        ),
    )

    assert result.mode is MethodologyGateMode.SHADOW
    assert result.analysis is analysis
    assert result.suppressed_candidate_count == 0
    assert result.reason_codes == ("METHODOLOGY_CANDIDATE_ROUTING_SHADOW",)
    assert len(result.decisions) == 1


def test_enforce_mode_removes_explicit_conflict_and_keeps_audit_record() -> None:
    result = apply_methodology_candidate_routing(
        _analysis(),
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.ALLOW),
            _decision(
                StrategyType.RANGE_REVERSAL,
                StrategyEnforcementAction.SUPPRESS,
            ),
        ),
        mode=MethodologyGateMode.ENFORCE,
    )

    assert tuple(item.strategy for item in result.analysis.candidates) == (
        StrategyType.TREND_PULLBACK,
    )
    assert len(result.analysis.candidate_actionability) == 1
    assert len(result.analysis.suppressed_candidates) == 1
    assert (
        result.analysis.suppressed_candidates[0].candidate.strategy is StrategyType.RANGE_REVERSAL
    )
    assert result.suppressed_candidate_count == 1
    assert result.suppressed_strategies == (StrategyType.RANGE_REVERSAL,)
    payload = methodology_candidate_routing_payload(result)
    assert payload["reason_codes"] == ["METHODOLOGY_CANDIDATES_SUPPRESSED"]
    assert payload["input_candidate_count"] == 2
    assert payload["retained_candidate_count"] == 1
    assert payload["lineage_balanced"] is True
    assert payload["all_generated_candidates_suppressed"] is False
    assert payload["suppressed_candidates"] == [
        {
            "candidate_id": "range_reversal:long:0",
            "strategy": StrategyType.RANGE_REVERSAL.value,
            "direction": "long",
            "entry_status": result.analysis.suppressed_candidates[0].entry_status.value,
            "suppression_stage": "methodology_enforcement",
            "terminal_outcome": "suppressed",
            "reason_codes": ["TEST_SUPPRESS"],
            "reasons": ["range_reversal is suppress"],
        }
    ]
    assert len(cast(list[object], payload["strategy_decisions"])) == 2


def test_all_candidates_suppressed_is_explicit() -> None:
    result = apply_methodology_candidate_routing(
        _analysis(),
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.SUPPRESS),
        ),
        mode=MethodologyGateMode.ENFORCE,
    )

    payload = methodology_candidate_routing_payload(result)

    assert result.analysis.candidates == ()
    assert payload["retained_candidate_count"] == 0
    assert payload["suppressed_candidate_count"] == 2
    assert payload["all_generated_candidates_suppressed"] is True


def test_deferred_or_missing_decision_remains_eligible() -> None:
    result = apply_methodology_candidate_routing(
        _analysis(),
        (_decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.DEFER),),
        mode=MethodologyGateMode.ENFORCE,
    )

    assert len(result.analysis.candidates) == 2
    assert result.suppressed_candidate_count == 0
    assert result.reason_codes == ("METHODOLOGY_CANDIDATE_ROUTING_NO_CHANGE",)


def test_missing_market_state_defers_and_preserves_candidates() -> None:
    result = evaluate_methodology_candidate_routing(
        _analysis(),
        market_state=None,
        mode=MethodologyGateMode.ENFORCE,
    )

    assert len(result.analysis.candidates) == 2
    assert result.suppressed_candidate_count == 0


def test_candidate_lane_context_prevents_broad_state_from_vetoing_local_scalp() -> None:
    result = evaluate_methodology_candidate_routing(
        _analysis(),
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.ENFORCE,
    )

    assert len(result.analysis.candidates) == 2
    assert result.suppressed_candidate_count == 0
    assert {item.candidate_id for item in result.decisions} == {
        "trend_pullback:long:0",
        "range_reversal:long:0",
    }
    decisions = {item.strategy: item for item in result.decisions}
    assert decisions[StrategyType.TREND_PULLBACK].action is StrategyEnforcementAction.DEFER
    assert decisions[StrategyType.TREND_PULLBACK].reason_codes == (
        "METHODOLOGY_METADATA_INCOMPLETE",
    )
    assert decisions[StrategyType.RANGE_REVERSAL].action is StrategyEnforcementAction.ALLOW


def test_prohibited_chaotic_state_still_suppresses_candidate_lanes() -> None:
    result = evaluate_methodology_candidate_routing(
        _analysis(),
        market_state=PrimaryMarketState.CHAOTIC,
        mode=MethodologyGateMode.ENFORCE,
    )

    assert tuple(item.strategy for item in result.analysis.candidates) == (
        StrategyType.TREND_PULLBACK,
    )
    assert result.suppressed_candidate_count == 1
    decisions = {item.strategy: item for item in result.decisions}
    assert decisions[StrategyType.TREND_PULLBACK].action is StrategyEnforcementAction.DEFER
    assert decisions[StrategyType.TREND_PULLBACK].reason_codes == (
        "METHODOLOGY_METADATA_INCOMPLETE",
    )
    assert decisions[StrategyType.RANGE_REVERSAL].action is StrategyEnforcementAction.SUPPRESS
    assert decisions[StrategyType.RANGE_REVERSAL].reason_codes == ("METHODOLOGY_PROHIBITED_STATE",)


def test_nearby_structured_retest_is_a_scalp_not_a_runner_veto() -> None:
    candidate = _candidate(
        StrategyType.BREAKOUT_RETEST,
        entry_mode=EntryMode.RETEST,
    )
    analysis = StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.BREAKOUT_RETEST,),
        eligible_strategies=(StrategyType.BREAKOUT_RETEST,),
        candidate_actionability=(
            CandidateActionability(
                candidate=candidate,
                status=EntryStatus.PULLBACK_PREFERRED,
            ),
        ),
    )

    result = evaluate_methodology_candidate_routing(
        analysis,
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.ENFORCE,
    )

    assert result.suppressed_candidate_count == 0
    assert result.decisions[0].action is StrategyEnforcementAction.ALLOW
    assert result.decisions[0].reason_codes == ("METHODOLOGY_COMPATIBLE_WITH_CONSTRAINTS",)


def test_routing_passes_measurable_lane_horizon_into_shared_context(
    monkeypatch: object,
) -> None:
    candidate = _candidate(StrategyType.TREND_PULLBACK)
    analysis = StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
        candidate_actionability=(
            CandidateActionability(
                candidate=candidate,
                status=EntryStatus.READY_NOW,
            ),
        ),
    )
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_assessment(
        candidate_arg: TradeCandidate,
        *,
        entry_status: object,
    ) -> object:
        assert candidate_arg is candidate
        assert entry_status is EntryStatus.READY_NOW
        return sentinel

    original_infer = candidate_routing.infer_candidate_methodology_context

    def capture_context(
        candidate_arg: TradeCandidate,
        *,
        entry_status: EntryStatus,
        lane_horizon: object | None = None,
    ) -> object:
        captured["candidate"] = candidate_arg
        captured["entry_status"] = entry_status
        captured["lane_horizon"] = lane_horizon
        return original_infer(
            candidate_arg,
            entry_status=entry_status,
            lane_horizon=None,
        )

    monkeypatch.setattr(
        candidate_routing,
        "_candidate_lane_horizon_assessment",
        fake_assessment,
    )
    monkeypatch.setattr(
        candidate_routing,
        "infer_candidate_methodology_context",
        capture_context,
    )

    result = evaluate_methodology_candidate_routing(
        analysis,
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.SHADOW,
    )

    assert result.input_candidate_count == 1
    assert captured == {
        "candidate": candidate,
        "entry_status": EntryStatus.READY_NOW,
        "lane_horizon": sentinel,
    }


def test_routing_preserves_legacy_context_when_measurement_is_unavailable(
    monkeypatch: object,
) -> None:
    candidate = _candidate(StrategyType.TREND_PULLBACK)
    analysis = StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
        candidate_actionability=(
            CandidateActionability(
                candidate=candidate,
                status=EntryStatus.READY_NOW,
            ),
        ),
    )
    captured: dict[str, object] = {}
    original_infer = candidate_routing.infer_candidate_methodology_context

    def unavailable(
        candidate_arg: TradeCandidate,
        *,
        entry_status: object,
    ) -> None:
        assert candidate_arg is candidate
        assert entry_status is EntryStatus.READY_NOW
        return None

    def capture_context(
        candidate_arg: TradeCandidate,
        *,
        entry_status: EntryStatus,
        lane_horizon: object | None = None,
    ) -> object:
        captured["lane_horizon"] = lane_horizon
        return original_infer(
            candidate_arg,
            entry_status=entry_status,
            lane_horizon=None,
        )

    monkeypatch.setattr(
        candidate_routing,
        "_candidate_lane_horizon_assessment",
        unavailable,
    )
    monkeypatch.setattr(
        candidate_routing,
        "infer_candidate_methodology_context",
        capture_context,
    )

    result = evaluate_methodology_candidate_routing(
        analysis,
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.SHADOW,
    )

    assert result.input_candidate_count == 1
    assert captured["lane_horizon"] is None


def test_geometry_safety_audit_is_shadow_only_and_preserved_in_payload() -> None:
    result = evaluate_methodology_candidate_routing(
        _analysis(),
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.SHADOW,
    )

    assert len(result.analysis.candidates) == 2
    assert len(result.geometry_safety_audits) == 2
    assert all(item.assessment is None for item in result.geometry_safety_audits)
    payload = methodology_candidate_routing_payload(result)
    audits = cast(list[dict[str, object]], payload["geometry_safety_audits"])
    assert len(audits) == 2
    assert all(item["shadow_only"] is True for item in audits)
    assert all(item["available"] is False for item in audits)


def test_geometry_coverage_reports_missing_inputs_and_blocks_enforcement_readiness() -> None:
    result = evaluate_methodology_candidate_routing(
        _analysis(),
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.SHADOW,
    )

    payload = methodology_candidate_routing_payload(result)
    coverage = cast(dict[str, object], payload["geometry_safety_coverage"])
    assert coverage["candidate_count"] == 2
    assert coverage["available_count"] == 0
    assert coverage["unavailable_count"] == 2
    assert coverage["enforcement_ready"] is False
    assert coverage["missing_measurement_counts"] == {"metadata": 2}


def _layered_state(
    relationship: TimeframeRelationship,
    severity: RelationshipSeverity,
) -> LayeredStateSnapshot:
    return LayeredStateSnapshot(
        execution_state=ExecutionState.CLEAN,
        setup_state=SetupState.PULLBACK,
        context_state=ContextState.TRENDING_UP,
        timeframe_relationship=relationship,
        relationship_severity=severity,
    )


def test_unavailable_htf_state_preserves_legacy_routing() -> None:
    assert _htf_assessment_from_layered_state(LayeredStateSnapshot()) is None


def test_mild_mixed_htf_state_reconstructs_constrained_assessment() -> None:
    assessment = _htf_assessment_from_layered_state(
        _layered_state(
            TimeframeRelationship.MIXED,
            RelationshipSeverity.MILD,
        )
    )

    assert assessment is not None
    assert assessment.confirmation_required is False
    assert assessment.target_ceiling_required is True
    assert assessment.hard_reject is False


def test_routing_passes_layered_state_and_mild_htf_consequence(monkeypatch) -> None:
    layered = _layered_state(
        TimeframeRelationship.MIXED,
        RelationshipSeverity.MILD,
    )
    candidate = _candidate(
        StrategyType.TREND_PULLBACK,
        layered_state=layered,
    )
    analysis = StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
        candidate_actionability=(
            CandidateActionability(candidate=candidate, status=EntryStatus.READY_NOW),
        ),
    )
    captured: dict[str, object] = {}
    original = candidate_routing.evaluate_strategy_eligibility

    def capture(*args: object, **kwargs: object) -> object:
        captured["layered_state"] = kwargs.get("layered_state")
        captured["htf_consequence"] = kwargs.get("htf_consequence")
        return original(*args, **kwargs)

    monkeypatch.setattr(candidate_routing, "evaluate_strategy_eligibility", capture)

    result = evaluate_methodology_candidate_routing(
        analysis,
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.SHADOW,
    )

    assert result.input_candidate_count == 1
    assert captured["layered_state"] is layered
    consequence = captured["htf_consequence"]
    assert consequence is not None
    assert consequence.allowed is True
    assert consequence.runner_allowed is False
    assert consequence.confirmation_required is False
    assert consequence.target_ceiling_r_multiple == 2.5


def test_countertrend_relationship_rejects_non_scalp_lane(monkeypatch) -> None:
    layered = LayeredStateSnapshot(
        execution_state=ExecutionState.CLEAN,
        setup_state=SetupState.RANGE,
        context_state=ContextState.RANGE_BOUND,
        timeframe_relationship=TimeframeRelationship.COUNTERTREND_SCALP,
        relationship_severity=RelationshipSeverity.STRONG,
    )
    candidate = _candidate(
        StrategyType.RANGE_REVERSAL,
        layered_state=layered,
    )
    analysis = StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 18, tzinfo=UTC),
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.RANGE_REVERSAL,),
        eligible_strategies=(StrategyType.RANGE_REVERSAL,),
        candidate_actionability=(
            CandidateActionability(candidate=candidate, status=EntryStatus.READY_NOW),
        ),
    )

    monkeypatch.setattr(
        candidate_routing,
        "infer_candidate_methodology_context",
        lambda *args, **kwargs: type(
            "_Context",
            (),
            {
                "lane": OpportunityLane.RUNNER,
                "holding_horizon": HoldingHorizon.RUNNER,
            },
        )(),
    )

    result = evaluate_methodology_candidate_routing(
        analysis,
        market_state=PrimaryMarketState.TRENDING_UP,
        mode=MethodologyGateMode.ENFORCE,
    )

    assert result.suppressed_candidate_count == 1
    assert result.decisions[0].action is StrategyEnforcementAction.SUPPRESS
    assert result.decisions[0].reason_codes == ("METHODOLOGY_PROHIBITED_STATE",)
