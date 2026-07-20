from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from apex.application.discovery_analysis import _methodology_parity_diagnostics
from apex.application.methodology_candidate_routing import (
    apply_methodology_candidate_routing,
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


def test_shadow_live_routing_exposes_enforcement_preview_without_mutation() -> None:
    routed = _analysis()
    live = apply_methodology_candidate_routing(
        routed,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.ALLOW),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.SUPPRESS),
        ),
        mode=MethodologyGateMode.SHADOW,
    )

    payload = _methodology_parity_diagnostics(routed, live)

    assert live.analysis is routed
    assert len(live.analysis.candidates) == 2
    assert payload == {
        "shadow_candidate_count": 2,
        "enforced_candidate_count": 1,
        "suppressed_candidate_count": 1,
        "suppressed_strategies": [StrategyType.RANGE_REVERSAL.value],
        "would_change_candidate_set": True,
        "all_candidates_would_be_suppressed": False,
        "reason_codes": ["METHODOLOGY_ENFORCEMENT_WOULD_CHANGE_CANDIDATES"],
    }


def test_enforce_live_routing_uses_same_pre_ranking_parity_baseline() -> None:
    routed = _analysis()
    live = apply_methodology_candidate_routing(
        routed,
        (
            _decision(StrategyType.TREND_PULLBACK, StrategyEnforcementAction.ALLOW),
            _decision(StrategyType.RANGE_REVERSAL, StrategyEnforcementAction.SUPPRESS),
        ),
        mode=MethodologyGateMode.ENFORCE,
    )

    payload = _methodology_parity_diagnostics(routed, live)

    assert len(live.analysis.candidates) == 1
    assert payload["shadow_candidate_count"] == 2
    assert payload["enforced_candidate_count"] == 1
    assert payload["suppressed_candidate_count"] == 1
    assert payload["would_change_candidate_set"] is True
