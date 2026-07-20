from __future__ import annotations

from datetime import UTC, datetime

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
from apex.strategies.opportunity_lifecycle import OpportunityStage
from apex.strategies.opportunity_plan_comparison import (
    CurrentPlanObservation,
    PlanChangeKind,
    PlanComparisonStatus,
    audit_original_plan_comparison,
    snapshot_original_plan,
)
from apex.strategies.opportunity_runner import (
    RunnerDecision,
    RunnerLifecycleAudit,
    RunnerReason,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate() -> TradeCandidate:
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.MARKET_NEAR,
            rationale=("fixture entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=95.0,
            rationale=("fixture invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=105.0,
                    label="tp1",
                    rationale=("first target",),
                ),
                TargetLevel(
                    kind=TargetType.LIQUIDITY,
                    price=110.0,
                    label="tp2",
                    rationale=("second target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=1.0,
            structure_quality=1.0,
            entry_quality=1.0,
            momentum_quality=1.0,
            volume_quality=1.0,
            liquidity_quality=1.0,
            target_space_quality=1.0,
        ),
        evidence=StrategyEvidence(
            supporting=("breakout accepted", "volume expanded"),
            contradictions=("higher-timeframe resistance",),
        ),
        metadata={},
    )


def test_snapshot_preserves_original_geometry_and_identity() -> None:
    candidate = _candidate()

    snapshot = snapshot_original_plan(
        candidate,
        lifecycle_stage=OpportunityStage.CMP,
    )

    assert snapshot.setup_id == candidate.lifecycle.cooldown_key
    assert snapshot.entry_lower == 99.0
    assert snapshot.entry_upper == 101.0
    assert snapshot.preferred_entry == 100.0
    assert snapshot.structural_invalidation == 95.0
    assert snapshot.targets == (105.0, 110.0)
    assert snapshot.lifecycle_stage is OpportunityStage.CMP


def test_unchanged_plan_reports_no_changes() -> None:
    original = snapshot_original_plan(_candidate())

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.DEVELOPING,
            achieved_target_labels=(),
            evidence=original.evidence,
        ),
    )

    assert audit.status is PlanComparisonStatus.UNCHANGED
    assert audit.changes == ()


def test_target_and_runner_progress_are_reported() -> None:
    original = snapshot_original_plan(
        _candidate(),
        lifecycle_stage=OpportunityStage.CMP,
    )
    runner = RunnerLifecycleAudit(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        decision=RunnerDecision.HOLD_RUNNER,
        reasons=(
            RunnerReason.STRUCTURE_INTACT,
            RunnerReason.CONTINUATION_HEALTHY,
            RunnerReason.TARGET_ROOM_AVAILABLE,
        ),
        protect_reference=None,
    )

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.CMP,
            achieved_target_labels=("tp1",),
            evidence=original.evidence,
            runner=runner,
        ),
    )

    assert audit.status is PlanComparisonStatus.PROGRESSED
    assert tuple(change.kind for change in audit.changes) == (
        PlanChangeKind.TARGET_ACHIEVED,
        PlanChangeKind.RUNNER_HOLD,
    )


def test_added_contradiction_marks_plan_degraded() -> None:
    original = snapshot_original_plan(_candidate())
    current_evidence = StrategyEvidence(
        supporting=original.evidence.supporting,
        contradictions=(
            *original.evidence.contradictions,
            "opposite reclaim forming",
        ),
    )

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.ARMED,
            achieved_target_labels=(),
            evidence=current_evidence,
        ),
    )

    assert audit.status is PlanComparisonStatus.DEGRADED
    assert audit.added_contradictions == ("opposite reclaim forming",)
    assert PlanChangeKind.CONTRADICTION_ADDED in {change.kind for change in audit.changes}


def test_removed_support_marks_plan_degraded() -> None:
    original = snapshot_original_plan(_candidate())
    current_evidence = StrategyEvidence(
        supporting=("breakout accepted",),
        contradictions=original.evidence.contradictions,
    )

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.ARMED,
            achieved_target_labels=(),
            evidence=current_evidence,
        ),
    )

    assert audit.status is PlanComparisonStatus.DEGRADED
    assert audit.removed_support == ("volume expanded",)


def test_terminal_stage_has_precedence_over_progress() -> None:
    original = snapshot_original_plan(_candidate())

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.INVALIDATED,
            achieved_target_labels=("tp1",),
            evidence=original.evidence,
        ),
    )

    assert audit.status is PlanComparisonStatus.TERMINAL
    assert audit.current_stage is OpportunityStage.INVALIDATED


def test_evidence_differences_are_deterministic() -> None:
    original = snapshot_original_plan(_candidate())
    current_evidence = StrategyEvidence(
        supporting=("new support z", "breakout accepted", "new support a"),
        contradictions=("new contradiction z", "new contradiction a"),
    )

    audit = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.ARMED,
            achieved_target_labels=(),
            evidence=current_evidence,
        ),
    )

    assert audit.added_support == ("new support a", "new support z")
    assert audit.removed_support == ("volume expanded",)
    assert audit.added_contradictions == (
        "new contradiction a",
        "new contradiction z",
    )
    assert audit.removed_contradictions == ("higher-timeframe resistance",)


def test_comparison_does_not_mutate_candidate_or_snapshot() -> None:
    candidate = _candidate()
    original = snapshot_original_plan(candidate)
    original_entry = candidate.entry
    original_lifecycle = candidate.lifecycle
    original_evidence = original.evidence

    audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.ARMED,
            achieved_target_labels=(),
            evidence=original.evidence,
        ),
    )

    assert candidate.entry is original_entry
    assert candidate.lifecycle is original_lifecycle
    assert original.evidence is original_evidence
