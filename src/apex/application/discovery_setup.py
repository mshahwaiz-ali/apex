"""Build discovery-neutral trade plans from selected candidates."""

from __future__ import annotations

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    StopQualityBand,
    TakeProfit,
)
from apex.application.trade_geometry import build_layered_targets, build_stop_geometry
from apex.scoring.contracts import CandidateSelectionResult
from apex.scoring.quality_dimensions import derive_quality_dimensions
from apex.scoring.selection import is_entry_status_executable
from apex.strategies import classify_candidate_actionability
from apex.strategies.contracts import (
    EntryZone,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry_status import EntryStatus

DEFAULT_MAXIMUM_CHASE_PCT = 0.35
DEFAULT_STRUCTURAL_STOP_BUFFER_PCT = 0.10
DEFAULT_STRUCTURAL_STOP_BUFFER_ATR = 0.25


def build_discovery_assessment(
    candidate_selection: CandidateSelectionResult,
) -> DiscoveryAssessment:
    """Convert candidate selection into a discovery assessment."""

    selected = candidate_selection.selected_candidate
    if selected is None:
        return DiscoveryAssessment(
            symbol=candidate_selection.symbol,
            decision_time=candidate_selection.decision_time,
            setup=None,
            reasons=(
                candidate_selection.no_trade_reason or "candidate selection produced no setup",
            ),
        )

    candidate = selected.candidate
    entry_status = classify_candidate_actionability(candidate)
    entry = _entry_zone(candidate.entry, candidate.direction)
    entry_opportunities = tuple(
        _entry_zone(opportunity, candidate.direction)
        for opportunity in candidate.entry_opportunities
    )
    stop = _stop(candidate)
    targets = _targets(candidate, stop)
    lifecycle = candidate.lifecycle
    expiry_seconds = None if lifecycle is None else lifecycle.expires_after_seconds
    return DiscoveryAssessment(
        symbol=candidate_selection.symbol,
        decision_time=candidate_selection.decision_time,
        setup=DiscoverySetup(
            symbol=candidate.symbol,
            direction=candidate.direction,
            strategy=candidate.strategy,
            entry_status=entry_status,
            decision_time=candidate.decision_time,
            candidate_id=selected.scored.candidate_id,
            confidence_score=selected.final_score,
            entry=entry,
            stop_loss=stop,
            take_profits=targets,
            management_policies=_management_policies(targets),
            warnings=tuple(candidate.evidence.warnings),
            quality_dimensions=derive_quality_dimensions(candidate.quality),
            execution_allowed_now=is_entry_status_executable(entry_status),
            entry_opportunities=entry_opportunities,
            setup_expiry_seconds=expiry_seconds,
            setup_expiry_reason=_expiry_reason(candidate),
            trader_headline=_trader_headline(entry_status),
        ),
    )


def _entry_zone(zone: EntryZone, direction: TradeDirection) -> ActionableEntry:
    configured_chase = zone.max_chase_price
    if configured_chase is None:
        offset = zone.preferred * DEFAULT_MAXIMUM_CHASE_PCT / 100.0
        configured_chase = (
            zone.upper + offset if direction is TradeDirection.LONG else zone.lower - offset
        )
    return ActionableEntry(
        lower=zone.lower,
        upper=zone.upper,
        preferred=zone.preferred,
        current_price=zone.current_price,
        maximum_chase_price=configured_chase,
        current_price_inside_zone=zone.lower <= zone.current_price <= zone.upper,
    )


def _stop(candidate: TradeCandidate) -> StopLoss:
    preferred = candidate.entry.preferred
    raw_atr = candidate.metadata.get("decision_atr")
    atr = (
        float(raw_atr)
        if isinstance(raw_atr, int | float) and not isinstance(raw_atr, bool) and raw_atr > 0
        else None
    )
    geometry = build_stop_geometry(
        direction=candidate.direction,
        preferred_entry=preferred,
        invalidation_price=candidate.invalidation.price,
        invalidation_type=candidate.invalidation.kind,
        atr=atr,
        minimum_buffer_pct=DEFAULT_STRUCTURAL_STOP_BUFFER_PCT,
        structural_buffer_atr=DEFAULT_STRUCTURAL_STOP_BUFFER_ATR,
    )
    quality_score = max(
        0.0,
        min(
            1.0,
            candidate.quality.structure_quality * 0.65 + candidate.quality.entry_quality * 0.35,
        ),
    )
    quality_band = (
        StopQualityBand.STRONG
        if quality_score >= 0.75
        else StopQualityBand.ACCEPTABLE
        if quality_score >= 0.45
        else StopQualityBand.WEAK
    )
    return StopLoss(
        price=geometry.price,
        distance=geometry.distance,
        distance_pct=geometry.distance_pct,
        rationale=(
            *candidate.invalidation.rationale,
            geometry.buffer_reason,
        ),
        quality_score=quality_score,
        quality_band=quality_band,
        invalidation_type=candidate.invalidation.kind,
        buffer_rationale=geometry.buffer_reason,
    )


def _targets(candidate: TradeCandidate, stop: StopLoss) -> tuple[TakeProfit, ...]:
    preferred = candidate.entry.preferred
    levels = build_layered_targets(
        direction=candidate.direction,
        preferred_entry=preferred,
        stop_price=stop.price,
        strategy_targets=candidate.targets.levels,
    )
    partials = _partial_close_percentages(len(levels))
    return tuple(
        TakeProfit(
            label=level.label,
            price=level.price,
            reward=abs(level.price - preferred),
            risk_reward=abs(level.price - preferred) / stop.distance,
            rationale=level.rationale,
            partial_close_pct=partial,
            target_type=level.kind,
            purpose=_target_purpose(level.kind, level.label),
        )
        for level, partial in zip(levels, partials, strict=True)
    )


def _target_purpose(kind: TargetType, label: str) -> str:
    if kind is TargetType.PARTIAL:
        return "risk-reduction partial"
    if kind is TargetType.EXPANSION:
        return "conditional extension target"
    if label.upper() == "TP1":
        return "first structural objective"
    return "primary structural objective"


def _expiry_reason(candidate: TradeCandidate) -> str:
    explicit = candidate.entry.expires_after_seconds is not None
    source = (
        "explicit strategy entry expiry" if explicit else "strategy and entry-mode validity policy"
    )
    return f"{source}: {candidate.strategy.value} / {candidate.entry.mode.value}"


def _trader_headline(status: EntryStatus) -> str:
    if status is EntryStatus.READY_NOW:
        return "Strong setup — executable now"
    if status is EntryStatus.AGGRESSIVE_NOW:
        return "Strong setup — aggressive execution possible"
    if status is EntryStatus.PULLBACK_PREFERRED:
        return "Strong setup — pullback/retest/reclaim pending"
    if status is EntryStatus.WATCH_NEAR_ENTRY:
        return "Developing setup — watch only"
    if status in {EntryStatus.LATE_OR_CHASING, EntryStatus.INVALIDATED}:
        return "Late or invalidated setup"
    return "No defensible setup found"


def _partial_close_percentages(count: int) -> tuple[float, ...]:
    if count <= 0:
        raise ValueError("target count must be positive")
    if count == 1:
        return (100.0,)
    if count == 2:
        return (50.0, 50.0)
    return (40.0, 35.0, *(25.0 / (count - 2) for _ in range(count - 2)))


def _management_policies(targets: tuple[TakeProfit, ...]) -> tuple[ManagementPolicy, ...]:
    first_target = targets[0]
    final_target = targets[-1]
    return (
        ManagementPolicy(
            kind=ManagementPolicyType.BREAKEVEN,
            trigger=f"{first_target.label} touched or trade reaches 1R",
            action="protect the entry after partial realization",
            rationale=("preserve the confirmed structural edge",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TRAILING,
            trigger=f"price accepts beyond {first_target.label}",
            action="trail behind the latest valid structural swing",
            rationale=("retain continuation potential without abandoning structure",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TIME_EXIT,
            trigger="the candidate expires without expected activation",
            action="cancel or exit the stale setup",
            rationale=("avoid carrying a thesis beyond its analysis window",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.MOMENTUM_FAILURE,
            trigger=f"momentum contradicts before {final_target.label}",
            action="reduce or exit before structural invalidation",
            rationale=("respond when continuation evidence fails",),
        ),
    )
