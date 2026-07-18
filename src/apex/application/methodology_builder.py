"""Build canonical methodology snapshots from existing selected candidates."""

from __future__ import annotations

from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    ConfidenceBasis,
    ConfidenceLabel,
    Contradiction,
    DurationExpectation,
    EntryOpportunity,
    EntryOpportunityType,
    EvidenceFamily,
    HoldCategory,
    InvalidationRule,
    StructuralInvalidation,
    TargetCandidate,
    TargetRole,
)
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    SetupMaturity,
)
from apex.scoring.contracts import CandidateSelectionResult
from apex.strategies import classify_candidate_actionability
from apex.strategies.contracts import EntryMode, TradeCandidate
from apex.strategies.entry_status import EntryStatus

_ENTRY_KIND_BY_MODE: dict[EntryMode, EntryOpportunityType] = {
    EntryMode.MARKET_NEAR: EntryOpportunityType.IMMEDIATE,
    EntryMode.PULLBACK: EntryOpportunityType.PULLBACK,
    EntryMode.RETEST: EntryOpportunityType.RETEST,
    EntryMode.SWEEP_RECOVERY: EntryOpportunityType.RECLAIM,
    EntryMode.MOMENTUM_CONTINUATION: EntryOpportunityType.AGGRESSIVE,
    EntryMode.SCALED_ENTRY: EntryOpportunityType.PREFERRED_NEARBY,
}

_CONFIRMATION_BY_MODE: dict[EntryMode, ConfirmationPolicy] = {
    EntryMode.MARKET_NEAR: ConfirmationPolicy.INTRABAR_ALLOWED,
    EntryMode.PULLBACK: ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
    EntryMode.RETEST: ConfirmationPolicy.RETEST_REQUIRED,
    EntryMode.SWEEP_RECOVERY: ConfirmationPolicy.RECLAIM_REQUIRED,
    EntryMode.MOMENTUM_CONTINUATION: ConfirmationPolicy.MIXED,
    EntryMode.SCALED_ENTRY: ConfirmationPolicy.MIXED,
}

_MATURITY_BY_STATUS: dict[EntryStatus, SetupMaturity] = {
    EntryStatus.READY_NOW: SetupMaturity.ENTRY_AVAILABLE,
    EntryStatus.AGGRESSIVE_NOW: SetupMaturity.ENTRY_AVAILABLE,
    EntryStatus.PULLBACK_PREFERRED: SetupMaturity.RETEST_PENDING,
    EntryStatus.WATCH_NEAR_ENTRY: SetupMaturity.PATTERN_DEVELOPING,
    EntryStatus.LATE_OR_CHASING: SetupMaturity.ENTRY_LATE,
    EntryStatus.INVALIDATED: SetupMaturity.INVALIDATED,
}


def build_methodology_snapshot(
    selection: CandidateSelectionResult,
) -> MethodologySnapshot:
    """Mirror the current selected-candidate result into canonical contracts.

    This builder deliberately introduces no new approval gates. It records the
    decision already made by the existing scoring and selection pipeline.
    """

    selected = selection.selected_candidate
    if selected is None:
        return MethodologySnapshot()

    candidate = selected.candidate
    status = classify_candidate_actionability(candidate)
    stop_price = _buffered_stop_price(candidate)
    entry = _entry(candidate)
    invalidation = StructuralInvalidation(
        price=stop_price,
        rule=InvalidationRule.CLOSE,
        structure="; ".join(candidate.invalidation.rationale),
        failure_event="setup thesis is invalidated beyond the structural level",
        volatility_buffer=abs(stop_price - candidate.invalidation.price),
        estimated_slippage=0.0,
    )
    evidence = strategy_evidence_observations(candidate.evidence)
    contradictions = tuple(
        Contradiction(
            code=f"legacy_contradiction_{index:03d}",
            family=EvidenceFamily.STRUCTURE,
            severity=0.5,
            reason=reason,
        )
        for index, reason in enumerate(candidate.evidence.contradictions, start=1)
    )
    targets = tuple(
        TargetCandidate(
            role=_target_role(index, len(candidate.targets.levels)),
            price=level.price,
            source="; ".join(level.rationale),
            expected_move_percentage=(
                abs(level.price - candidate.entry.preferred)
                / candidate.entry.preferred
                * 100.0
            ),
            risk_multiple=(
                abs(level.price - candidate.entry.preferred)
                / abs(candidate.entry.preferred - stop_price)
            ),
            conditional=index > 2,
        )
        for index, level in enumerate(candidate.targets.levels, start=1)
    )
    expiry_seconds = candidate.lifecycle.expires_after_seconds
    confidence_label = _confidence_label(selected.final_score)

    return MethodologySnapshot(
        setup_maturity=_MATURITY_BY_STATUS[status],
        confirmation_policy=_CONFIRMATION_BY_MODE[candidate.entry.mode],
        evidence=evidence,
        contradictions=contradictions,
        entry_opportunities=(entry,),
        invalidation=invalidation,
        targets=targets,
        duration=DurationExpectation(
            category=_hold_category(expiry_seconds),
            expected_hold_min_seconds=max(60, expiry_seconds // 3),
            expected_hold_max_seconds=expiry_seconds,
            expected_bars=max(1, expiry_seconds // 60),
            setup_expiry_bars=max(1, expiry_seconds // 60),
            expiry_reason="existing candidate lifecycle expiry",
        ),
        confidence=ConfidenceAssessment(
            setup=confidence_label,
            execution=confidence_label,
            target=confidence_label,
            data=ConfidenceLabel.MODERATE,
            historical=ConfidenceLabel.VERY_LOW,
            overall=confidence_label,
            basis=ConfidenceBasis.INSUFFICIENT_CALIBRATION,
            strongest_support=candidate.evidence.supporting[0],
            strongest_contradiction=(
                candidate.evidence.contradictions[0]
                if candidate.evidence.contradictions
                else None
            ),
            missing_evidence=("historical calibration",),
        ),
    )


def _entry(candidate: TradeCandidate) -> EntryOpportunity:
    maximum_chase = candidate.entry.max_chase_price
    if maximum_chase is None:
        maximum_chase = (
            candidate.entry.upper
            if candidate.direction.value == "long"
            else candidate.entry.lower
        )
    return EntryOpportunity(
        kind=_ENTRY_KIND_BY_MODE[candidate.entry.mode],
        zone_low=candidate.entry.lower,
        zone_high=candidate.entry.upper,
        ideal_entry=candidate.entry.preferred,
        confirmation_level=None,
        maximum_chase=maximum_chase,
        current_distance_percentage=(
            candidate.entry.distance_from_current
            / candidate.entry.current_price
            * 100.0
        ),
        current_distance_atr=candidate.entry.atr_distance,
        quality=candidate.entry.location_quality,
        reason="; ".join(candidate.entry.rationale),
        expiry_bars=max(1, candidate.lifecycle.expires_after_seconds // 60),
    )


def _buffered_stop_price(candidate: TradeCandidate) -> float:
    buffer = candidate.entry.preferred * 0.10 / 100.0
    if candidate.direction.value == "long":
        return candidate.invalidation.price - buffer
    return candidate.invalidation.price + buffer


def _target_role(index: int, count: int) -> TargetRole:
    if index == 1:
        return TargetRole.TP1
    if index == 2:
        return TargetRole.TP2
    if index == 3 and count == 3:
        return TargetRole.TP3
    return TargetRole.RUNNER


def _confidence_label(score: float) -> ConfidenceLabel:
    if score >= 85.0:
        return ConfidenceLabel.VERY_HIGH
    if score >= 70.0:
        return ConfidenceLabel.HIGH
    if score >= 50.0:
        return ConfidenceLabel.MODERATE
    if score >= 30.0:
        return ConfidenceLabel.LOW
    return ConfidenceLabel.VERY_LOW


def _hold_category(expiry_seconds: int) -> HoldCategory:
    if expiry_seconds <= 300:
        return HoldCategory.MICRO_SCALP
    if expiry_seconds <= 1800:
        return HoldCategory.SCALP
    if expiry_seconds <= 14_400:
        return HoldCategory.INTRADAY
    if expiry_seconds <= 86_400:
        return HoldCategory.MULTI_SESSION
    return HoldCategory.SWING


__all__ = ["build_methodology_snapshot"]