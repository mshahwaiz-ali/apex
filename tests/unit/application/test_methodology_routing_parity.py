from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from apex.application.methodology_candidate_routing import (
    evaluate_methodology_routing_parity,
    methodology_routing_parity_payload,
)
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
            decision_time=datetime(2026, 7, 20, tzinfo=UTC),
            evidence=StrategyEvidence(
                supporting=("structure supports the setup",),
                structure_references=("structure",),
            ),
        ),
    )


def _analysis() -> StrategyAnalysisResult:
    trend = _candidate(StrategyType.TREND_PULLBACK)
    reversal = _candidate(StrategyType.RANGE_REVERSAL)
    candidates = (trend, reversal)
    return StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 20, tzinfo=UTC),
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


def test_parity_audit_reports_no_candidate_change() -> None:
    audit = evaluate_methodology_routing_parity(
        _analysis(),
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.ALLOW),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.DEFER),
        ),
    )

    assert audit.shadow_candidate_count == 2
    assert audit.enforced_candidate_count == 2
    assert audit.suppressed_candidate_count == 0
    assert audit.suppressed_strategies == ()
    assert audit.would_change_candidate_set is False
    assert audit.all_candidates_would_be_suppressed is False
    assert audit.reason_codes == ("METHODOLOGY_ENFORCEMENT_PARITY",)


def test_parity_audit_reports_partial_suppression() -> None:
    audit = evaluate_methodology_routing_parity(
        _analysis(),
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.ALLOW),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.SUPPRESS),
        ),
    )
    payload = methodology_routing_parity_payload(audit)

    assert audit.shadow_candidate_count == 2
    assert audit.enforced_candidate_count == 1
    assert audit.suppressed_candidate_count == 1
    assert audit.suppressed_strategies == (StrategyType.RANGE_REVERSAL,)
    assert audit.would_change_candidate_set is True
    assert audit.all_candidates_would_be_suppressed is False
    assert payload["suppressed_strategies"] == [StrategyType.RANGE_REVERSAL.value]
    assert payload["reason_codes"] == ["METHODOLOGY_ENFORCEMENT_WOULD_CHANGE_CANDIDATES"]


def test_parity_audit_reports_full_suppression() -> None:
    audit = evaluate_methodology_routing_parity(
        _analysis(),
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.SUPPRESS),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.SUPPRESS),
        ),
    )

    assert audit.enforced_candidate_count == 0
    assert audit.suppressed_candidate_count == 2
    assert audit.all_candidates_would_be_suppressed is True
