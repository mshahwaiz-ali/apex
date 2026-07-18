from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from apex.application.methodology_candidate_routing import (
    apply_methodology_candidate_routing,
    evaluate_methodology_candidate_routing,
    methodology_candidate_routing_payload,
)
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.strategies.analysis import CandidateActionability, StrategyAnalysisResult
from apex.strategies.contracts import StrategyEvidence, TradeCandidate, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True)
class _Candidate:
    symbol: str
    strategy: StrategyType
    direction: TradeDirection
    decision_time: datetime
    evidence: StrategyEvidence


def _candidate(strategy: StrategyType) -> TradeCandidate:
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
            ),
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
    assert result.analysis.suppressed_candidates[0].candidate.strategy is StrategyType.RANGE_REVERSAL
    assert result.suppressed_candidate_count == 1
    assert result.suppressed_strategies == (StrategyType.RANGE_REVERSAL,)
    payload = methodology_candidate_routing_payload(result)
    assert payload["reason_codes"] == ["METHODOLOGY_CANDIDATES_SUPPRESSED"]
    assert payload["retained_candidate_count"] == 1
    assert payload["all_generated_candidates_suppressed"] is False
    assert payload["suppressed_candidates"] == [
        {
            "strategy": StrategyType.RANGE_REVERSAL.value,
            "direction": "long",
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
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.DEFER),
        ),
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
