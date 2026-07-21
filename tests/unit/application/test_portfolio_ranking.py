from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.portfolio_ranking import (
    portfolio_rank_components,
    portfolio_ranking_key,
)
from apex.domain.methodology_contracts import (
    LayeredStateSnapshot,
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.scoring.quality_dimensions import CandidateQualityDimensions
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _setup(
    candidate_id: str,
    *,
    risk_reward: float = 2.0,
    execution_allowed_now: bool = True,
    target_quality: float = 80.0,
    relationship: TimeframeRelationship = TimeframeRelationship.WITH_TREND,
    severity: RelationshipSeverity = RelationshipSeverity.NONE,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.MOMENTUM_SCALP,
        entry_status=(
            EntryStatus.READY_NOW if execution_allowed_now else EntryStatus.WATCH_NEAR_ENTRY
        ),
        decision_time=datetime(2026, 7, 21, tzinfo=UTC),
        candidate_id=candidate_id,
        confidence_score=75.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=100.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=98.0,
            distance=2.0,
            distance_pct=2.0,
            rationale=("structure",),
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=100.0 + risk_reward * 2.0,
                reward=risk_reward * 2.0,
                risk_reward=risk_reward,
                rationale=("structure",),
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.TIME_EXIT,
                trigger="expiry",
                action="exit",
                rationale=("bounded lifecycle",),
            ),
        ),
        quality_dimensions=CandidateQualityDimensions(
            setup_quality=80.0,
            execution_quality=80.0,
            target_quality=target_quality,
            risk_quality=80.0,
            overall_trade_quality=80.0,
        ),
        execution_allowed_now=execution_allowed_now,
        layered_state=LayeredStateSnapshot(
            timeframe_relationship=relationship,
            relationship_severity=severity,
        ),
    )


def test_better_valid_setup_ranks_above_weaker_setup() -> None:
    better = _setup("better", risk_reward=2.2, target_quality=90.0)
    weaker = _setup("weaker", risk_reward=1.2, target_quality=60.0)

    assert portfolio_ranking_key(better) < portfolio_ranking_key(weaker)
    assert (
        portfolio_rank_components(better).rank_score > portfolio_rank_components(weaker).rank_score
    )


def test_executable_setup_ranks_above_equivalent_nearby_setup() -> None:
    executable = _setup("executable", execution_allowed_now=True)
    nearby = _setup("nearby", execution_allowed_now=False)

    assert portfolio_ranking_key(executable) < portfolio_ranking_key(nearby)


def test_poor_reward_cannot_rank_highly() -> None:
    good = _setup("good", risk_reward=2.0)
    poor = _setup("poor", risk_reward=0.25)

    assert portfolio_rank_components(poor).tp1_reward_quality < 10.0
    assert portfolio_ranking_key(good) < portfolio_ranking_key(poor)


def test_htf_conflict_reduces_rank_without_making_setup_ineligible() -> None:
    aligned = _setup("aligned")
    conflict = _setup(
        "conflict",
        relationship=TimeframeRelationship.COUNTERTREND_SCALP,
        severity=RelationshipSeverity.STRONG,
    )

    assert (
        portfolio_rank_components(aligned).htf_alignment
        > portfolio_rank_components(conflict).htf_alignment
    )
    assert portfolio_ranking_key(aligned) < portfolio_ranking_key(conflict)


def test_stable_tie_breaker_is_candidate_identity() -> None:
    left = _setup("a")
    right = replace(left, candidate_id="b")

    assert sorted((right, left), key=portfolio_ranking_key) == [left, right]


def test_unavailable_rank_evidence_remains_explicitly_unavailable() -> None:
    setup = _setup("unavailable-evidence")
    setup = replace(
        setup,
        layered_state=replace(
            setup.layered_state,
            timeframe_relationship=TimeframeRelationship.UNAVAILABLE,
            relationship_severity=RelationshipSeverity.UNAVAILABLE,
        ),
    )
    components = portfolio_rank_components(setup)

    assert components.timing_quality is None
    assert components.data_confidence is None
    assert components.htf_alignment is None
    payload = components.to_dict()
    assert payload["timing_quality"] is None
    assert payload["data_confidence"] is None
    assert payload["htf_alignment"] is None
    assert 0.0 <= components.rank_score <= 100.0
