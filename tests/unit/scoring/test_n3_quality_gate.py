"""Focused tests for the futures standard-mode quality pass."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from apex.config import StrategyApprovalConfig, load_strategy_approval_config
from apex.domain import EntryState, RiskMode
from apex.scoring import (
    ApprovalReasonCode,
    QualityGateReasonCode,
    ScoreBreakdown,
    ScoredCandidate,
    SetupEligibility,
    evaluate_candidate_quality_gate,
    evaluate_strategy_approval,
)
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)


def _config() -> StrategyApprovalConfig:
    return load_strategy_approval_config(Path("config/strategy_approval.yaml"))


def _scored_candidate(
    *,
    strategy: StrategyType,
    score: float,
    entry_mode: EntryMode,
    extension_penalty: float = 0.1,
    volume_quality: float = 0.8,
    momentum_quality: float = 0.8,
    target_space_quality: float = 0.8,
    provisional: bool = False,
) -> ScoredCandidate:
    candidate = TradeCandidate(
        symbol="BTCUSDT",
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 14, tzinfo=UTC),
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=entry_mode,
            rationale=("controlled test entry",),
            max_chase_price=102.0,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("structure fails below support",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=105.0,
                    label="TP1",
                    rationale=("next structural resistance",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=momentum_quality,
            volume_quality=volume_quality,
            liquidity_quality=0.8,
            target_space_quality=target_space_quality,
            extension_penalty=extension_penalty,
        ),
        evidence=StrategyEvidence(supporting=("fixture evidence",)),
        metadata={},
        provisional=provisional,
    )
    return ScoredCandidate(
        candidate_id=f"{strategy.value}-{entry_mode.value}",
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points={"fixture": score},
            penalty_points={},
            base_score=score,
            total_penalty=0.0,
            final_score=score,
        ),
        normalized_metrics={},
    )


def test_standard_approved_setup_without_historical_edge_is_paper_only() -> None:
    decision = evaluate_strategy_approval(
        strategy=StrategyType.TREND_PULLBACK,
        risk_mode=RiskMode.STANDARD,
        score=80.0,
        entry_state=EntryState.READY_NOW,
        config=_config(),
    )

    assert decision.approved is True
    assert decision.eligibility is SetupEligibility.PAPER_ONLY
    assert ApprovalReasonCode.HISTORICAL_EVIDENCE_INSUFFICIENT in {
        reason.code for reason in decision.reasons
    }


def test_standard_historical_edge_still_requires_forward_paper_evidence() -> None:
    decision = evaluate_strategy_approval(
        strategy=StrategyType.TREND_PULLBACK,
        risk_mode=RiskMode.STANDARD,
        score=80.0,
        entry_state=EntryState.READY_NOW,
        config=_config(),
        historical_evidence_available=True,
    )

    assert decision.approved is True
    assert decision.eligibility is SetupEligibility.PAPER_ONLY
    assert ApprovalReasonCode.FORWARD_PAPER_EVIDENCE_REQUIRED in {
        reason.code for reason in decision.reasons
    }


def test_strategy_score_below_mode_threshold_is_rejected() -> None:
    decision = evaluate_strategy_approval(
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        risk_mode=RiskMode.STANDARD,
        score=59.0,
        entry_state=EntryState.READY_NOW,
        config=_config(),
    )

    assert decision.approved is False
    assert decision.eligibility is SetupEligibility.REJECTED
    assert decision.reasons[0].code is ApprovalReasonCode.STRATEGY_SCORE_BELOW_MODE_THRESHOLD
    assert "59.00" in decision.reasons[0].message
    assert "60.00" in decision.reasons[0].message


def test_breakout_retest_uses_controlled_threshold_adjustment() -> None:
    decision = evaluate_candidate_quality_gate(
        _scored_candidate(
            strategy=StrategyType.BREAKOUT_CONTINUATION,
            score=53.0,
            entry_mode=EntryMode.RETEST,
        ),
        risk_mode=RiskMode.STANDARD,
        config=_config(),
    )

    assert decision.approved is True
    assert decision.required_score == 52.0
    assert QualityGateReasonCode.BREAKOUT_RETEST_PREFERRED in {
        reason.code for reason in decision.reasons
    }


def test_direct_breakout_requires_volume_and_target_space() -> None:
    decision = evaluate_candidate_quality_gate(
        _scored_candidate(
            strategy=StrategyType.BREAKOUT_CONTINUATION,
            score=90.0,
            entry_mode=EntryMode.MARKET_NEAR,
            volume_quality=0.5,
            target_space_quality=0.5,
        ),
        risk_mode=RiskMode.STANDARD,
        config=_config(),
    )

    assert decision.approved is False
    blocking_codes = {reason.code for reason in decision.reasons if reason.blocking}
    warning_codes = {reason.code for reason in decision.reasons if not reason.blocking}
    assert QualityGateReasonCode.DIRECT_BREAKOUT_VOLUME_TOO_WEAK in warning_codes
    assert QualityGateReasonCode.DIRECT_BREAKOUT_TARGET_SPACE_INSUFFICIENT in blocking_codes

def test_momentum_confirmation_shortfalls_are_warnings_above_floor() -> None:
    decision = evaluate_candidate_quality_gate(
        _scored_candidate(
            strategy=StrategyType.MOMENTUM_CONTINUATION,
            score=54.0,
            entry_mode=EntryMode.MOMENTUM_CONTINUATION,
            volume_quality=0.5,
            momentum_quality=0.5,
        ),
        risk_mode=RiskMode.STANDARD,
        config=_config(),
    )

    assert decision.approved is True
    warning_codes = {reason.code for reason in decision.reasons if not reason.blocking}
    assert QualityGateReasonCode.MOMENTUM_VOLUME_CONFIRMATION_MISSING in warning_codes
    assert QualityGateReasonCode.MOMENTUM_QUALITY_INSUFFICIENT in warning_codes

