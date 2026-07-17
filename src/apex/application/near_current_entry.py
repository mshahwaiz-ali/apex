"""Environment-aware near-current entry decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    PreferredDirection,
    strategy_allowed_for_direction,
)
from apex.market_environment import ExtensionState, MarketEnvironment, VolatilityState
from apex.strategies import StrategyType, TradeDirection


class ChaseRisk(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class EntryActionability(StrEnum):
    """Simplified user-facing entry status."""

    READY = "READY"
    AGGRESSIVE = "AGGRESSIVE"
    PULLBACK_PREFERRED = "PULLBACK_PREFERRED"
    WATCH = "WATCH"
    LATE = "LATE"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class NearCurrentEntryDecision:
    """Actionability overlay for an existing precision-entry plan."""

    entry_state: str
    actionability: EntryActionability
    actionable_now: bool
    immediate_entry_price: float | None
    preferred_entry_price: float | None
    preferred_direction: PreferredDirection
    entry_zone_low: float | None
    entry_zone_high: float | None
    ideal_entry: float | None
    maximum_chase_price: float | None
    current_price: float | None
    distance_from_ideal_pct: float | None
    reclaim_trigger: float | None
    retest_trigger: float | None
    structural_invalidation: float | None
    entry_quality_score: float | None
    chase_risk: ChaseRisk | None
    warning_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]


def evaluate_near_current_entry(
    precision_entry: Mapping[str, Any] | None,
    environment: MarketEnvironment,
    route: MarketStrategyRoute,
    *,
    selected_strategy: StrategyType | None = None,
    selected_direction: TradeDirection | None = None,
) -> NearCurrentEntryDecision:
    """Combine precision geometry with market-environment actionability."""

    if precision_entry is None:
        return NearCurrentEntryDecision(
            entry_state="NO_TRADE",
            actionability=EntryActionability.INVALID,
            actionable_now=False,
            immediate_entry_price=None,
            preferred_entry_price=None,
            preferred_direction=route.preferred_direction,
            entry_zone_low=None,
            entry_zone_high=None,
            ideal_entry=None,
            maximum_chase_price=None,
            current_price=None,
            distance_from_ideal_pct=None,
            reclaim_trigger=None,
            retest_trigger=None,
            structural_invalidation=None,
            entry_quality_score=None,
            chase_risk=None,
            warning_codes=(),
            warnings=(),
            reason_codes=("PRECISION_ENTRY_UNAVAILABLE",),
            reasons=("No approved precision-entry geometry is available",),
        )

    state = str(precision_entry.get("entry_state", "NO_TRADE"))
    base_score = _number(precision_entry.get("score")) or 0.0
    distance_pct = _number(precision_entry.get("current_distance_from_ideal_pct"))
    codes: list[str] = []
    reasons: list[str] = []
    warning_codes: list[str] = []
    warnings: list[str] = []
    score = base_score

    route_allows_setup = (
        selected_strategy is None
        or selected_direction is None
        or strategy_allowed_for_direction(route, selected_strategy, selected_direction)
    )
    if not environment.tradeable:
        state = "NO_TRADE"
        score = 0.0
        codes.append("ENVIRONMENT_BLOCKED_ENTRY")
        reasons.append("Fused market environment is not tradeable for a new entry")
    else:
        score = score * 0.65 + route.routing_score * 0.35
        codes.append("ENVIRONMENT_ENTRY_SCORE_APPLIED")
        reasons.append("Precision quality was blended with environment routing confidence")
        if not route_allows_setup:
            score -= 20.0
            warning_codes.append("SELECTED_SETUP_ROUTE_CONFLICT")
            warnings.append(
                "Selected strategy or direction conflicts with the preferred market route"
            )
        if route.preferred_direction is PreferredDirection.NONE:
            score -= 15.0
            warning_codes.append("NO_PREFERRED_ROUTE_DIRECTION")
            warnings.append("Market route has no preferred direction")

    chase_risk = _chase_risk(distance_pct, environment)
    if state != "NO_TRADE":
        if chase_risk is ChaseRisk.EXTREME and state not in {"INVALIDATED", "MISSED_ENTRY"}:
            state = "MISSED_ENTRY"
            score = min(score, 35.0)
            codes.append("MAXIMUM_CHASE_RISK")
            reasons.append("Current price is too extended for a controlled near-current entry")
        elif chase_risk is ChaseRisk.HIGH and state == "READY_NOW":
            score = min(score, 60.0)
            warning_codes.append("READY_NOW_HIGH_CHASE_RISK")
            warnings.append(
                "Entry is geometrically valid, but a pullback offers better execution"
            )

    if environment.extension_state in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
        score -= 15.0
        warning_codes.append("ENVIRONMENT_EXTENSION_WARNING")
        warnings.append("Environment extension reduced near-current entry quality")
    if environment.volatility_state is VolatilityState.EXTREME:
        score -= 10.0
        warning_codes.append("ENVIRONMENT_VOLATILITY_WARNING")
        warnings.append("Extreme volatility reduced entry quality")

    actionability = _entry_actionability(
        state=state,
        score=score,
        chase_risk=chase_risk,
        has_warnings=bool(warnings),
    )
    if actionability is EntryActionability.AGGRESSIVE and state in {
        "WAIT_FOR_RETEST",
        "WAIT_FOR_RECLAIM",
    }:
        warning_codes.append("EARLY_ENTRY_BEFORE_CONFIRMATION")
        warnings.append(
            "Current price is close enough for a controlled early entry before full confirmation"
        )
    actionable = actionability in {
        EntryActionability.READY,
        EntryActionability.AGGRESSIVE,
    }
    if actionable:
        codes.append("ENTRY_ACTIONABLE_NOW")
        reasons.append("Entry is available near current price")
    current_price = _number(precision_entry.get("current_price"))
    ideal_entry = _number(precision_entry.get("ideal_entry"))

    return NearCurrentEntryDecision(
        entry_state=state,
        actionability=actionability,
        actionable_now=actionable,
        immediate_entry_price=current_price if actionable else None,
        preferred_entry_price=ideal_entry,
        preferred_direction=route.preferred_direction,
        entry_zone_low=_number(precision_entry.get("entry_zone_low")),
        entry_zone_high=_number(precision_entry.get("entry_zone_high")),
        ideal_entry=_number(precision_entry.get("ideal_entry")),
        maximum_chase_price=_number(precision_entry.get("maximum_chase_price")),
        current_price=_number(precision_entry.get("current_price")),
        distance_from_ideal_pct=distance_pct,
        reclaim_trigger=_number(precision_entry.get("reclaim_trigger")),
        retest_trigger=_number(precision_entry.get("retest_trigger")),
        structural_invalidation=_number(precision_entry.get("structural_invalidation")),
        entry_quality_score=round(max(0.0, min(100.0, score)), 6),
        chase_risk=chase_risk,
        warning_codes=tuple(dict.fromkeys(warning_codes)),
        warnings=tuple(dict.fromkeys(warnings)),
        reason_codes=tuple(dict.fromkeys(codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def near_current_entry_payload(decision: NearCurrentEntryDecision) -> dict[str, object]:
    """Serialize a near-current entry decision."""

    return {
        "entry_state": decision.entry_state,
        "actionability": decision.actionability.value,
        "actionable_now": decision.actionable_now,
        "immediate_entry_price": decision.immediate_entry_price,
        "preferred_entry_price": decision.preferred_entry_price,
        "preferred_direction": decision.preferred_direction.value,
        "entry_zone_low": decision.entry_zone_low,
        "entry_zone_high": decision.entry_zone_high,
        "ideal_entry": decision.ideal_entry,
        "maximum_chase_price": decision.maximum_chase_price,
        "current_price": decision.current_price,
        "distance_from_ideal_pct": decision.distance_from_ideal_pct,
        "reclaim_trigger": decision.reclaim_trigger,
        "retest_trigger": decision.retest_trigger,
        "structural_invalidation": decision.structural_invalidation,
        "entry_quality_score": decision.entry_quality_score,
        "chase_risk": decision.chase_risk.value if decision.chase_risk is not None else None,
        "warning_codes": list(decision.warning_codes),
        "warnings": list(decision.warnings),
        "reason_codes": list(decision.reason_codes),
        "reasons": list(decision.reasons),
    }


def _entry_actionability(
    *,
    state: str,
    score: float,
    chase_risk: ChaseRisk,
    has_warnings: bool,
) -> EntryActionability:
    if state in {"NO_TRADE", "INVALIDATED"}:
        return EntryActionability.INVALID
    if state == "MISSED_ENTRY" or chase_risk is ChaseRisk.EXTREME:
        return EntryActionability.LATE
    if state == "READY_NOW":
        if chase_risk is ChaseRisk.HIGH or score < 55.0:
            return EntryActionability.PULLBACK_PREFERRED
        if has_warnings or score < 70.0:
            return EntryActionability.AGGRESSIVE
        return EntryActionability.READY
    if state in {"WAIT_FOR_RETEST", "WAIT_FOR_RECLAIM"}:
        if chase_risk in {ChaseRisk.LOW, ChaseRisk.MODERATE} and score >= 65.0:
            return EntryActionability.AGGRESSIVE
        return EntryActionability.PULLBACK_PREFERRED
    if state == "APPROACHING_ENTRY":
        if chase_risk is ChaseRisk.LOW and score >= 70.0:
            return EntryActionability.AGGRESSIVE
        return EntryActionability.WATCH
    return EntryActionability.WATCH


def _chase_risk(distance_pct: float | None, environment: MarketEnvironment) -> ChaseRisk:
    if environment.extension_state is ExtensionState.EXTREME:
        return ChaseRisk.EXTREME
    if distance_pct is None:
        return ChaseRisk.HIGH
    if distance_pct <= 0.15:
        return ChaseRisk.LOW
    if distance_pct <= 0.40:
        return ChaseRisk.MODERATE
    if distance_pct <= 0.80:
        return ChaseRisk.HIGH
    return ChaseRisk.EXTREME


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
