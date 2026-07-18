"""Project existing discovery setups into canonical methodology snapshots."""

from __future__ import annotations

from dataclasses import replace

from apex.application.discovery_contracts import DiscoverySetup, SymbolAnalysis
from apex.application.market_state import MarketStateSnapshot
from apex.application.market_usability import (
    MarketUsabilityAssessment,
    classify_market_usability,
)
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    ConfidenceBasis,
    ConfidenceLabel,
    DurationExpectation,
    EntryOpportunity,
    EntryOpportunityType,
    HoldCategory,
    InvalidationRule,
    StructuralInvalidation,
    TargetCandidate,
    TargetRole,
)
from apex.application.methodology_market_state import adapt_market_state
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import ConfirmationPolicy, SetupMaturity
from apex.strategies.entry_status import EntryStatus

_MATURITY_BY_STATUS: dict[EntryStatus, SetupMaturity] = {
    EntryStatus.READY_NOW: SetupMaturity.ENTRY_AVAILABLE,
    EntryStatus.AGGRESSIVE_NOW: SetupMaturity.ENTRY_AVAILABLE,
    EntryStatus.PULLBACK_PREFERRED: SetupMaturity.RETEST_PENDING,
    EntryStatus.WATCH_NEAR_ENTRY: SetupMaturity.PATTERN_DEVELOPING,
    EntryStatus.LATE_OR_CHASING: SetupMaturity.ENTRY_LATE,
    EntryStatus.INVALIDATED: SetupMaturity.INVALIDATED,
}

_ENTRY_KIND_BY_STATUS: dict[EntryStatus, EntryOpportunityType] = {
    EntryStatus.READY_NOW: EntryOpportunityType.IMMEDIATE,
    EntryStatus.AGGRESSIVE_NOW: EntryOpportunityType.AGGRESSIVE,
    EntryStatus.PULLBACK_PREFERRED: EntryOpportunityType.PULLBACK,
    EntryStatus.WATCH_NEAR_ENTRY: EntryOpportunityType.DEVELOPING_FUTURE,
    EntryStatus.LATE_OR_CHASING: EntryOpportunityType.PREFERRED_NEARBY,
    EntryStatus.INVALIDATED: EntryOpportunityType.DEVELOPING_FUTURE,
}


def project_analysis_methodology(analysis: SymbolAnalysis) -> MethodologySnapshot:
    """Return stored methodology or a compatibility projection from the setup."""

    usability = classify_market_usability(analysis.data_quality_by_timeframe)
    methodology = analysis.methodology
    if methodology is None:
        setup = analysis.assessment.setup
        methodology = (
            MethodologySnapshot(market_usability=usability)
            if setup is None
            else _project_setup(setup, market_usability=usability)
        )
    elif methodology.market_usability is None:
        methodology = replace(methodology, market_usability=usability)

    fused_state = getattr(analysis, "market_state", None)
    if methodology.market_state is None and isinstance(fused_state, MarketStateSnapshot):
        methodology = replace(methodology, market_state=adapt_market_state(fused_state))
    return methodology


def _project_setup(
    setup: DiscoverySetup,
    *,
    market_usability: MarketUsabilityAssessment,
) -> MethodologySnapshot:
    confidence = _confidence_label(setup.confidence_score)
    target_count = len(setup.take_profits)
    expiry_bars = max(1, len(setup.management_policies))
    return MethodologySnapshot(
        market_usability=market_usability,
        setup_maturity=_MATURITY_BY_STATUS[setup.entry_status],
        confirmation_policy=_confirmation_policy(setup.entry_status),
        entry_opportunities=(
            EntryOpportunity(
                kind=_ENTRY_KIND_BY_STATUS[setup.entry_status],
                zone_low=setup.entry.lower,
                zone_high=setup.entry.upper,
                ideal_entry=setup.entry.preferred,
                confirmation_level=None,
                maximum_chase=setup.entry.maximum_chase_price,
                current_distance_percentage=(
                    abs(setup.entry.current_price - setup.entry.preferred)
                    / setup.entry.current_price
                    * 100.0
                ),
                current_distance_atr=0.0,
                quality=max(0.0, min(1.0, setup.stop_loss.quality_score)),
                reason="existing discovery entry geometry",
                expiry_bars=expiry_bars,
            ),
        ),
        invalidation=StructuralInvalidation(
            price=setup.stop_loss.price,
            rule=InvalidationRule.CLOSE,
            structure="; ".join(setup.stop_loss.rationale),
            failure_event="price closes beyond the existing structural stop",
            volatility_buffer=0.0,
            estimated_slippage=0.0,
        ),
        targets=tuple(
            TargetCandidate(
                role=_target_role(index, target_count),
                price=target.price,
                source="; ".join(target.rationale),
                expected_move_percentage=(
                    abs(target.price - setup.entry.preferred)
                    / setup.entry.preferred
                    * 100.0
                ),
                risk_multiple=target.risk_reward,
                conditional=index > 2,
            )
            for index, target in enumerate(setup.take_profits, start=1)
        ),
        duration=DurationExpectation(
            category=_hold_category(expiry_bars),
            expected_hold_min_seconds=max(60, expiry_bars * 20),
            expected_hold_max_seconds=max(60, expiry_bars * 60),
            expected_bars=expiry_bars,
            setup_expiry_bars=expiry_bars,
            expiry_reason="existing setup management time-exit policy",
        ),
        confidence=ConfidenceAssessment(
            setup=confidence,
            execution=confidence,
            target=confidence,
            data=ConfidenceLabel.MODERATE,
            historical=ConfidenceLabel.VERY_LOW,
            overall=confidence,
            basis=ConfidenceBasis.INSUFFICIENT_CALIBRATION,
            strongest_support="existing selected candidate passed current scoring",
            strongest_contradiction=(setup.warnings[0] if setup.warnings else None),
            missing_evidence=("historical calibration", "independent evidence metadata"),
        ),
    )


def _confirmation_policy(status: EntryStatus) -> ConfirmationPolicy:
    if status is EntryStatus.PULLBACK_PREFERRED:
        return ConfirmationPolicy.RETEST_REQUIRED
    if status is EntryStatus.WATCH_NEAR_ENTRY:
        return ConfirmationPolicy.CLOSE_REQUIRED
    if status is EntryStatus.AGGRESSIVE_NOW:
        return ConfirmationPolicy.INTRABAR_ALLOWED
    return ConfirmationPolicy.MIXED


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


def _hold_category(expiry_bars: int) -> HoldCategory:
    if expiry_bars <= 3:
        return HoldCategory.MICRO_SCALP
    if expiry_bars <= 10:
        return HoldCategory.SCALP
    if expiry_bars <= 48:
        return HoldCategory.INTRADAY
    if expiry_bars <= 144:
        return HoldCategory.MULTI_SESSION
    return HoldCategory.SWING


__all__ = ["project_analysis_methodology"]