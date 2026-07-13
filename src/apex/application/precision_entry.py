"""Build precision-entry plans from approved futures setups."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain import (
    EntryClassificationInput,
    FuturesDirection,
    PrecisionEntryPlan,
    classify_entry_state,
    weighted_precision_score,
)
from apex.risk.contracts import RiskApprovedSetup
from apex.strategies import TimeframeContext, TimeframeRole


@dataclass(frozen=True, slots=True)
class PrecisionTriggerContext:
    reclaim_trigger: float
    retest_trigger: float
    fast_failure_trigger: float
    trigger_timeframes: tuple[str, ...]
    trigger_state: str
    trigger_evidence: tuple[str, ...]
    missing_data_warnings: tuple[str, ...]


def build_precision_entry_plan(
    setup: RiskApprovedSetup,
    *,
    timeframe_contexts: Sequence[TimeframeContext] = (),
) -> PrecisionEntryPlan:
    """Return a deterministic precision-entry plan for one approved setup."""

    direction = FuturesDirection(setup.direction.value.upper())
    triggers = _precision_triggers(
        setup,
        direction=direction,
        timeframe_contexts=timeframe_contexts,
    )
    spread_penalty, spread_warnings = _spread_penalty(timeframe_contexts)
    liquidity_quality, trap_penalty, microstructure_warnings = _microstructure_quality(
        timeframe_contexts,
        direction=direction,
    )
    classification = classify_entry_state(
        EntryClassificationInput(
            direction=direction,
            current_price=setup.entry.current_price,
            zone_low=setup.entry.lower,
            zone_high=setup.entry.upper,
            ideal_entry=setup.entry.preferred,
            maximum_chase_price=setup.entry.maximum_chase_price,
            reclaim_trigger=triggers.reclaim_trigger,
            retest_trigger=triggers.retest_trigger,
            structural_invalidation=setup.stop_loss.price,
        )
    )
    distance = abs(setup.entry.current_price - setup.entry.preferred)
    distance_pct = distance / setup.entry.preferred * 100.0
    zone_width = max(1e-12, setup.entry.upper - setup.entry.lower)
    distance_score = max(0.0, min(100.0, 100.0 - distance / zone_width * 50.0))
    score = weighted_precision_score(
        structural_quality=setup.stop_loss.quality_score * 100.0,
        liquidity_quality=liquidity_quality,
        momentum_alignment=min(100.0, setup.confidence_score),
        volatility_suitability=80.0,
        distance_from_ideal=distance_score,
        extension_penalty=25.0 if setup.entry.current_price_inside_zone else 10.0,
        trap_penalty=trap_penalty,
        spread_slippage_penalty=spread_penalty,
        multi_timeframe_agreement=min(100.0, setup.confidence_score),
    )
    return PrecisionEntryPlan(
        entry_state=classification.state.value,
        entry_zone_low=setup.entry.lower,
        entry_zone_high=setup.entry.upper,
        ideal_entry=setup.entry.preferred,
        current_price=setup.entry.current_price,
        current_distance_from_ideal=distance,
        current_distance_from_ideal_pct=distance_pct,
        maximum_chase_price=setup.entry.maximum_chase_price,
        reclaim_trigger=triggers.reclaim_trigger,
        retest_trigger=triggers.retest_trigger,
        fast_failure_trigger=triggers.fast_failure_trigger,
        trigger_timeframes=triggers.trigger_timeframes,
        trigger_state=triggers.trigger_state,
        trigger_evidence=triggers.trigger_evidence,
        structural_invalidation=setup.stop_loss.price,
        expected_time_to_entry=_expected_time_to_entry(classification.state.value),
        actionability_explanation=classification.reasons[0],
        missing_data_warnings=(
            *triggers.missing_data_warnings,
            *spread_warnings,
            *microstructure_warnings,
        ),
        score=score,
        classification=classification,
    )


def _expected_time_to_entry(entry_state: str) -> str:
    if entry_state == "READY_NOW":
        return "now"
    if entry_state in {"APPROACHING_ENTRY", "WAIT_FOR_RETEST", "WAIT_FOR_RECLAIM"}:
        return "near"
    if entry_state == "WATCH":
        return "later"
    return "not_actionable"


def _precision_triggers(
    setup: RiskApprovedSetup,
    *,
    direction: FuturesDirection,
    timeframe_contexts: Sequence[TimeframeContext],
) -> PrecisionTriggerContext:
    frames = tuple(
        frame
        for frame in timeframe_contexts
        if frame.timeframe in {"5m", "3m", "1m"}
        or frame.role in {TimeframeRole.ENTRY, TimeframeRole.REFINEMENT, TimeframeRole.TIMING}
    )
    reclaim_trigger = setup.entry.upper if direction is FuturesDirection.LONG else setup.entry.lower
    retest_trigger = setup.entry.preferred
    fast_failure_trigger = (
        setup.entry.lower if direction is FuturesDirection.LONG else setup.entry.upper
    )
    evidence: list[str] = []
    missing: list[str] = []
    if not frames:
        missing.append("5m/3m/1m precision trigger context unavailable")
        return PrecisionTriggerContext(
            reclaim_trigger=reclaim_trigger,
            retest_trigger=retest_trigger,
            fast_failure_trigger=fast_failure_trigger,
            trigger_timeframes=(),
            trigger_state="UNAVAILABLE",
            trigger_evidence=tuple(evidence),
            missing_data_warnings=tuple(missing),
        )

    reclaim_votes = retest_votes = failure_votes = stale_votes = 0
    for frame in frames:
        price = frame.current_price
        slope = frame.features.rsi_slope or 0.0
        momentum = frame.features.rate_of_change or 0.0
        aligned = _momentum_aligned(direction, slope=slope, momentum=momentum)
        reclaim_active = (
            (price >= reclaim_trigger)
            if direction is FuturesDirection.LONG
            else (price <= reclaim_trigger)
        ) and aligned
        retest_active = _near(price, retest_trigger, tolerance_pct=0.15)
        failure_active = (
            price < fast_failure_trigger
            if direction is FuturesDirection.LONG
            else price > fast_failure_trigger
        )
        reclaim_votes += int(reclaim_active)
        retest_votes += int(retest_active)
        failure_votes += int(failure_active)
        stale_votes += int(frame.is_stale or frame.data_confidence < 0.75)
        if reclaim_active:
            evidence.append(f"{frame.timeframe} reclaim confirmed with aligned momentum")
        if retest_active:
            evidence.append(f"{frame.timeframe} retesting ideal entry")
        if failure_active:
            evidence.append(f"{frame.timeframe} fast failure beyond trigger")
        if frame.is_stale:
            evidence.append(f"{frame.timeframe} trigger data is stale")

    if failure_votes:
        trigger_state = "FAST_FAILURE"
    elif reclaim_votes >= 2 or (reclaim_votes >= 1 and len(frames) == 1):
        trigger_state = "RECLAIM_CONFIRMED"
    elif retest_votes:
        trigger_state = "RETEST_ACTIVE"
    elif stale_votes == len(frames):
        trigger_state = "STALE"
    else:
        trigger_state = "WAITING"
    return PrecisionTriggerContext(
        reclaim_trigger=reclaim_trigger,
        retest_trigger=retest_trigger,
        fast_failure_trigger=fast_failure_trigger,
        trigger_timeframes=tuple(frame.timeframe for frame in frames),
        trigger_state=trigger_state,
        trigger_evidence=tuple(evidence),
        missing_data_warnings=tuple(missing),
    )


def _momentum_aligned(direction: FuturesDirection, *, slope: float, momentum: float) -> bool:
    if direction is FuturesDirection.LONG:
        return slope >= 0.0 and momentum >= 0.0
    return slope <= 0.0 and momentum <= 0.0


def _near(price: float, level: float, *, tolerance_pct: float) -> bool:
    return abs(price - level) / level * 100.0 <= tolerance_pct


def _spread_penalty(
    timeframe_contexts: Sequence[TimeframeContext],
) -> tuple[float, tuple[str, ...]]:
    spreads = tuple(
        frame.spread_percentage
        for frame in timeframe_contexts
        if frame.spread_percentage is not None
    )
    if not spreads:
        return 10.0, ("spread data unavailable",)
    best = min(spreads)
    if best <= 0.05:
        return 2.0, (f"best available spread {best:.4f}% is acceptable",)
    if best <= 0.15:
        return 6.0, (f"best available spread {best:.4f}% is elevated",)
    return 18.0, (f"best available spread {best:.4f}% is too wide for precision entry",)


def _microstructure_quality(
    timeframe_contexts: Sequence[TimeframeContext],
    *,
    direction: FuturesDirection,
) -> tuple[float, float, tuple[str, ...]]:
    frames = tuple(
        frame
        for frame in timeframe_contexts
        if frame.order_book_depth_imbalance is not None
        or frame.exchange_tick_size is not None
        or frame.exchange_step_size is not None
        or frame.exchange_min_notional is not None
        or frame.nearest_long_cluster_distance_pct is not None
        or frame.nearest_short_cluster_distance_pct is not None
    )
    warnings: list[str] = []
    imbalances = tuple(
        frame.order_book_depth_imbalance
        for frame in frames
        if frame.order_book_depth_imbalance is not None
    )
    if not imbalances:
        liquidity_quality = 65.0
        trap_penalty = 5.0
        warnings.append("order-book depth data unavailable")
    else:
        directional_imbalance = (
            max(imbalances) if direction is FuturesDirection.LONG else -min(imbalances)
        )
        if directional_imbalance >= 0.25:
            liquidity_quality = 88.0
            trap_penalty = 0.0
            warnings.append(
                f"order-book depth supports entry with imbalance {directional_imbalance:.3f}"
            )
        elif directional_imbalance <= -0.25:
            liquidity_quality = 45.0
            trap_penalty = 20.0
            warnings.append(
                f"order-book depth opposes entry with imbalance {directional_imbalance:.3f}"
            )
        else:
            liquidity_quality = 72.0
            trap_penalty = 6.0
            warnings.append(
                f"order-book depth is mixed with directional imbalance {directional_imbalance:.3f}"
            )

    if not any(
        frame.exchange_tick_size is not None
        and frame.exchange_step_size is not None
        and frame.exchange_min_notional is not None
        for frame in frames
    ):
        warnings.append("exact exchange-filter data unavailable")
    else:
        warnings.append("exchange precision and notional filters available")

    adverse_distances = tuple(
        distance
        for distance in (
            frame.nearest_long_cluster_distance_pct
            if direction is FuturesDirection.LONG
            else frame.nearest_short_cluster_distance_pct
            for frame in frames
        )
        if distance is not None
    )
    favorable_distances = tuple(
        distance
        for distance in (
            frame.nearest_short_cluster_distance_pct
            if direction is FuturesDirection.LONG
            else frame.nearest_long_cluster_distance_pct
            for frame in frames
        )
        if distance is not None
    )
    if not adverse_distances and not favorable_distances:
        warnings.append("liquidation-cluster data unavailable")
    else:
        if adverse_distances:
            nearest_adverse = min(adverse_distances)
            if nearest_adverse <= 0.50:
                trap_penalty = min(100.0, trap_penalty + 18.0)
                liquidity_quality = max(0.0, liquidity_quality - 10.0)
                warnings.append(f"adverse liquidation cluster is close at {nearest_adverse:.3f}%")
            else:
                warnings.append(
                    f"nearest adverse liquidation cluster is {nearest_adverse:.3f}% away"
                )
        if favorable_distances:
            nearest_favorable = min(favorable_distances)
            if nearest_favorable <= 1.50:
                liquidity_quality = min(100.0, liquidity_quality + 4.0)
                warnings.append(
                    f"favorable liquidation cluster magnet is {nearest_favorable:.3f}% away"
                )
            else:
                warnings.append(
                    f"nearest favorable liquidation cluster is {nearest_favorable:.3f}% away"
                )
    return liquidity_quality, trap_penalty, tuple(warnings)
