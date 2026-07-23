"""Explicit first-pullback continuation strategy family."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import EntryZone, StrategyEvidence, TradeCandidate
from apex.strategies.strategy_types import StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates


def generate_first_pullback_continuation_candidates(
    context: StrategyContext,
    *,
    decision_time: datetime,
) -> tuple[TradeCandidate, ...]:
    """Promote near-CMP pullbacks with a concrete continuation reference."""

    candidates = generate_trend_pullback_candidates(
        context,
        decision_time=decision_time,
    )
    promoted: list[TradeCandidate] = []
    for candidate in candidates:
        if int(candidate.metadata.get("reference_count", 0)) < 1:
            continue
        entry = _first_pullback_entry(candidate)
        if entry is None:
            continue
        promoted.append(_as_first_pullback(candidate, entry=entry))
    return tuple(promoted)


def _first_pullback_entry(candidate: TradeCandidate) -> EntryZone | None:
    """Select a valid near-CMP continuation zone independent of primary ranking."""

    opportunities = candidate.entry_opportunities or (candidate.entry,)
    eligible = tuple(
        zone
        for zone in opportunities
        if zone.atr_distance <= 1.0 and not zone.is_extended
    )
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda zone: (
            zone.atr_distance,
            -zone.location_quality,
            abs(zone.preferred - zone.current_price),
            zone.preferred,
        ),
    )


def _as_first_pullback(candidate: TradeCandidate, *, entry: EntryZone) -> TradeCandidate:
    metadata = {
        **dict(candidate.metadata),
        "strategy_family": StrategyType.FIRST_PULLBACK_CONTINUATION.value,
        "source_strategy": candidate.strategy.value,
        "selected_entry_source": "near_cmp_continuation_opportunity",
    }
    evidence = candidate.evidence
    return replace(
        candidate,
        strategy=StrategyType.FIRST_PULLBACK_CONTINUATION,
        entry=entry,
        evidence=StrategyEvidence(
            supporting=tuple(
                dict.fromkeys(
                    (
                        "first actionable pullback remains close to current price",
                        "at least one structural, EMA, or VWAP continuation reference is present",
                        *evidence.supporting,
                    )
                )
            ),
            contradictions=evidence.contradictions,
            warnings=evidence.warnings,
            feature_references=evidence.feature_references,
            structure_references=tuple(
                dict.fromkeys((*evidence.structure_references, "first_pullback"))
            ),
            liquidity_references=evidence.liquidity_references,
        ),
        metadata=metadata,
    )
