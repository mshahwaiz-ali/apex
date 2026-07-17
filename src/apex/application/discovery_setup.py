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
from apex.scoring.contracts import CandidateSelectionResult
from apex.strategies import classify_candidate_actionability
from apex.strategies.contracts import TradeCandidate, TradeDirection

DEFAULT_MAXIMUM_CHASE_PCT = 0.35
DEFAULT_STRUCTURAL_STOP_BUFFER_PCT = 0.10


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
            reasons=(candidate_selection.no_trade_reason or "candidate selection produced no setup",),
        )

    candidate = selected.candidate
    entry = _entry(candidate)
    stop = _stop(candidate)
    targets = _targets(candidate, stop)
    return DiscoveryAssessment(
        symbol=candidate_selection.symbol,
        decision_time=candidate_selection.decision_time,
        setup=DiscoverySetup(
            symbol=candidate.symbol,
            direction=candidate.direction,
            strategy=candidate.strategy,
            entry_status=classify_candidate_actionability(candidate),
            decision_time=candidate.decision_time,
            candidate_id=selected.scored.candidate_id,
            confidence_score=selected.final_score,
            entry=entry,
            stop_loss=stop,
            take_profits=targets,
            management_policies=_management_policies(targets),
            warnings=tuple(candidate.evidence.warnings),
        ),
    )


def _entry(candidate: TradeCandidate) -> ActionableEntry:
    configured_chase = candidate.entry.max_chase_price
    if configured_chase is None:
        offset = candidate.entry.preferred * DEFAULT_MAXIMUM_CHASE_PCT / 100.0
        configured_chase = (
            candidate.entry.upper + offset
            if candidate.direction is TradeDirection.LONG
            else candidate.entry.lower - offset
        )
    return ActionableEntry(
        lower=candidate.entry.lower,
        upper=candidate.entry.upper,
        preferred=candidate.entry.preferred,
        current_price=candidate.entry.current_price,
        maximum_chase_price=configured_chase,
        current_price_inside_zone=(
            candidate.entry.lower <= candidate.entry.current_price <= candidate.entry.upper
        ),
    )


def _stop(candidate: TradeCandidate) -> StopLoss:
    preferred = candidate.entry.preferred
    buffer = preferred * DEFAULT_STRUCTURAL_STOP_BUFFER_PCT / 100.0
    price = (
        candidate.invalidation.price - buffer
        if candidate.direction is TradeDirection.LONG
        else candidate.invalidation.price + buffer
    )
    distance = abs(preferred - price)
    quality_score = max(
        0.0,
        min(
            1.0,
            candidate.quality.structure_quality * 0.65
            + candidate.quality.entry_quality * 0.35,
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
        price=price,
        distance=distance,
        distance_pct=distance / preferred * 100.0,
        rationale=(*candidate.invalidation.rationale, "buffer beyond thesis invalidation"),
        quality_score=quality_score,
        quality_band=quality_band,
    )


def _targets(candidate: TradeCandidate, stop: StopLoss) -> tuple[TakeProfit, ...]:
    preferred = candidate.entry.preferred
    partials = _partial_close_percentages(len(candidate.targets.levels))
    return tuple(
        TakeProfit(
            label=level.label,
            price=level.price,
            reward=abs(level.price - preferred),
            risk_reward=abs(level.price - preferred) / stop.distance,
            rationale=level.rationale,
            partial_close_pct=partial,
        )
        for level, partial in zip(candidate.targets.levels, partials, strict=True)
    )


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
