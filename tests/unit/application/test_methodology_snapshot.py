from __future__ import annotations

from typing import cast

from apex.application.discovery_analysis import _build_native_methodology_snapshot
from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_contracts import (
    EntryOpportunity,
    EntryOpportunityType,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
    InvalidationRule,
    RejectionCode,
    RejectionReason,
    RejectionSeverity,
    StructuralInvalidation,
    TargetCandidate,
    TargetRole,
)
from apex.application.methodology_snapshot import (
    MethodologySnapshot,
    methodology_snapshot_payload,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyEvidence


def test_strategy_evidence_adapter_preserves_stable_category_order() -> None:
    observations = strategy_evidence_observations(
        StrategyEvidence(
            supporting=("trend structure intact",),
            contradictions=("near resistance",),
            warnings=("average participation",),
            feature_references=("rsi_slope",),
            structure_references=("prior_swing_high",),
            liquidity_references=("range_boundary",),
        )
    )

    assert [item.source for item in observations] == [
        "legacy_support_001",
        "legacy_contradiction_001",
        "legacy_warning_001",
        "legacy_feature_001",
        "legacy_structure_001",
        "legacy_liquidity_001",
    ]
    assert observations[0].effect is EvidenceEffect.SUPPORTS
    assert observations[1].effect is EvidenceEffect.CONTRADICTS


def test_methodology_snapshot_separates_blockers_and_penalties() -> None:
    snapshot = MethodologySnapshot(
        entry_opportunities=(
            EntryOpportunity(
                kind=EntryOpportunityType.IMMEDIATE,
                zone_low=99.0,
                zone_high=101.0,
                ideal_entry=100.0,
                confirmation_level=None,
                maximum_chase=102.0,
                current_distance_percentage=0.0,
                current_distance_atr=0.0,
                quality=0.8,
                reason="price is inside the structural entry zone",
                expiry_bars=3,
            ),
        ),
        invalidation=StructuralInvalidation(
            price=97.0,
            rule=InvalidationRule.CLOSE,
            structure="pullback swing low",
            failure_event="setup timeframe closes below the swing low",
            volatility_buffer=0.5,
            estimated_slippage=0.1,
        ),
        targets=(
            TargetCandidate(
                role=TargetRole.TP1,
                price=105.0,
                source="prior swing high",
                expected_move_percentage=5.0,
                risk_multiple=1.5,
            ),
        ),
        rejections=(
            RejectionReason(
                code=RejectionCode.AVERAGE_PARTICIPATION,
                severity=RejectionSeverity.SOFT_PENALTY,
                reason="participation is acceptable but not expanding",
                penalty=0.15,
            ),
        ),
    )

    payload = methodology_snapshot_payload(snapshot)

    assert snapshot.executable is True
    assert snapshot.hard_blockers == ()
    assert len(snapshot.soft_penalties) == 1
    assert payload["soft_penalties"] == ["average_participation"]
    assert payload["executable"] is True


def test_methodology_snapshot_hard_blocker_prevents_execution() -> None:
    snapshot = MethodologySnapshot(
        rejections=(
            RejectionReason(
                code=RejectionCode.NO_DEFINABLE_INVALIDATION,
                severity=RejectionSeverity.HARD_BLOCKER,
                reason="no structural failure level can be defined",
            ),
        )
    )

    assert snapshot.executable is False
    assert [item.code for item in snapshot.hard_blockers] == [
        RejectionCode.NO_DEFINABLE_INVALIDATION
    ]


def test_native_snapshot_deduplicates_identical_evidence() -> None:
    observation = EvidenceObservation(
        family=EvidenceFamily.STRUCTURE,
        source="setup_structure",
        normalized_strength=0.8,
        freshness=1.0,
        independence_group="structure",
        effect=EvidenceEffect.SUPPORTS,
        reason="setup structure remains intact",
    )

    snapshot = _build_native_methodology_snapshot(
        None,
        context=cast(StrategyContext, object()),
        evidence=(observation, observation),
        contradictions=(),
        no_trade_reason="no eligible setup",
    )

    assert snapshot.evidence == (observation,)
