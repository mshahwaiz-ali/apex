from __future__ import annotations

from datetime import UTC, datetime

from apex.application.runtime_precision import (
    RuntimePrecisionArtifact,
    RuntimePrecisionProfile,
    apply_runtime_precision_gate,
)
from apex.config.settings import PrecisionGateSettings
from apex.research.precision import (
    CandidateOutcomeLabel,
    build_candidate_feature_snapshot,
)
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

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _selection() -> CandidateSelectionResult:
    trade = TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=100.0,
            preferred=99.5,
            current_price=99.5,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=EntryMode.MARKET_NEAR,
            rationale=("inside existing structural entry",),
        ),
        invalidation=InvalidationConcept(
            InvalidationType.STRUCTURAL,
            97.0,
            ("existing structural invalidation",),
        ),
        targets=TargetConcept(
            (TargetLevel(TargetType.STRUCTURAL, 104.0, "TP1", ("existing target",)),)
        ),
        quality=RawQualityMetrics(0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8),
        evidence=StrategyEvidence(("existing evidence",)),
        metadata={},
    )
    scored = ScoredCandidate(
        "candidate-1",
        trade,
        ScoreBreakdown({"quality": 75.0}, {}, 75.0, 0.0, 75.0),
        {},
    )
    ranked = RankedCandidate(
        scored,
        1,
        CandidateOutcome.ACCEPTED,
        (),
        ("candidate-1",),
    )
    consensus = ConflictSummary(DirectionalConsensus.LONG, 1, 0, (), ())
    return CandidateSelectionResult(
        symbol="BTCUSDT",
        decision_time=NOW,
        all_scored_candidates=(scored,),
        ranked_candidates=(ranked,),
        rejected_candidates=(),
        conflict_summary=consensus,
        directional_consensus=DirectionalConsensus.LONG,
        selected_candidate=ranked,
        no_trade_reason=None,
        evaluated_strategy_order=(StrategyType.TREND_PULLBACK,),
        configuration_id="test",
        metadata={},
    )


def _artifact(*, historical: bool = True, paper: bool = True) -> RuntimePrecisionArtifact:
    return RuntimePrecisionArtifact(
        artifact_version="precision-v1",
        feature_schema_version="candidate-features-v1",
        dataset_fingerprint="dataset",
        configuration_hash="config",
        code_hash="code",
        attempted_configurations=2,
        historical_promoted=historical,
        paper_promoted=paper,
        frozen_before="2026-07-01T00:00:00+00:00",
        profiles=(
            RuntimePrecisionProfile(
                "trend_pullback|long|*|*",
                0.8,
                0.60,
                0.2,
                (-0.1, 0.5),
                300,
            ),
        ),
        artifact_sha256="digest",
    )


def test_observe_only_records_abstention_without_changing_selection() -> None:
    selection = _selection()

    updated, payload = apply_runtime_precision_gate(
        selection,
        _artifact(),
        PrecisionGateSettings(mode="observe_only"),
        regime="trend",
        cohort="liquid",
    )

    assert updated is selection
    assert payload["production_changed"] is False
    assert payload["selected_candidate_decision"]["state"] == "abstain"


def test_enforce_suppresses_low_confidence_candidate() -> None:
    updated, payload = apply_runtime_precision_gate(
        _selection(),
        _artifact(),
        PrecisionGateSettings(mode="enforce"),
        regime="trend",
        cohort="liquid",
    )

    assert updated.selected_candidate is None
    assert updated.no_trade_reason is not None
    assert payload["production_changed"] is True


def test_enforce_cannot_use_historically_only_promoted_artifact() -> None:
    updated, payload = apply_runtime_precision_gate(
        _selection(),
        _artifact(paper=False),
        PrecisionGateSettings(mode="enforce"),
        regime="trend",
        cohort="liquid",
        artifact_reasons=("paper_promotion_incomplete",),
    )

    assert updated.selected_candidate is None
    assert payload["enforcement_authorized"] is False
    assert "enforcement_not_authorized" in payload["reason_codes"]


def test_future_outcomes_cannot_change_frozen_candidate_features() -> None:
    ranked = _selection().ranked_candidates[0]
    first = build_candidate_feature_snapshot(
        ranked,
        configuration_hash="config",
        dataset_fingerprint="dataset",
        code_hash="code",
    )
    first_outcome = CandidateOutcomeLabel(
        first.feature_snapshot_id,
        NOW.replace(hour=1),
        True,
        1.0,
        "target",
        "historical_events",
    )
    second_outcome = CandidateOutcomeLabel(
        first.feature_snapshot_id,
        NOW.replace(hour=2),
        True,
        -1.0,
        "stop",
        "historical_events",
    )
    second = build_candidate_feature_snapshot(
        ranked,
        configuration_hash="config",
        dataset_fingerprint="dataset",
        code_hash="code",
    )

    assert first.feature_snapshot_id == second.feature_snapshot_id
    assert first_outcome.positive_net is True
    assert second_outcome.positive_net is False
