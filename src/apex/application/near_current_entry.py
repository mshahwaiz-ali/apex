"""Environment-aware near-current entry decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.market_strategy_router import MarketStrategyRoute, PreferredDirection
from apex.market_environment import ExtensionState, MarketEnvironment, VolatilityState


class ChaseRisk(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass(frozen=True, slots=True)
class NearCurrentEntryDecision:
    """Actionability overlay for an existing precision-entry plan."""

    entry_state: str
    actionable_now: bool
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
    entry_quality_score: float
    chase_risk: ChaseRisk
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]


def evaluate_near_current_entry(
    precision_entry: Mapping[str, Any] | None,
    environment: MarketEnvironment,
    route: MarketStrategyRoute,
) -> NearCurrentEntryDecision:
    """Combine precision geometry with market-environment actionability."""

    if precision_entry is None:
        return NearCurrentEntryDecision(
            entry_state="NO_TRADE",
            actionable_now=False,
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
            entry_quality_score=0.0,
            chase_risk=ChaseRisk.EXTREME,
            reason_codes=("PRECISION_ENTRY_UNAVAILABLE",),
            reasons=("No approved precision-entry geometry is available",),
        )

    state = str(precision_entry.get("entry_state", "NO_TRADE"))
    base_score = _number(precision_entry.get("score")) or 0.0
    distance_pct = _number(precision_entry.get("current_distance_from_ideal_pct"))
    codes: list[str] = []
    reasons: list[str] = []
    score = base_score

    if not environment.tradeable or route.preferred_direction is PreferredDirection.NONE:
        state = "NO_TRADE"
        score = 0.0
        codes.append("ENVIRONMENT_BLOCKED_ENTRY")
        reasons.append("Fused market environment blocks a new entry")
    else:
        score = score * 0.65 + route.routing_score * 0.35
        codes.append("ENVIRONMENT_ENTRY_SCORE_APPLIED")
        reasons.append("Precision quality was blended with environment routing confidence")

    chase_risk = _chase_risk(distance_pct, environment)
    if chase_risk is ChaseRisk.EXTREME and state not in {"INVALIDATED", "MISSED_ENTRY"}:
        state = "MISSED_ENTRY"
        score = min(score, 35.0)
        codes.append("MAXIMUM_CHASE_RISK")
        reasons.append("Current price is too extended for a controlled near-current entry")
    elif chase_risk is ChaseRisk.HIGH and state == "READY_NOW":
        state = "WAIT_FOR_RETEST"
        score = min(score, 60.0)
        codes.append("READY_NOW_DOWNGRADED_FOR_CHASE")
        reasons.append("Entry is geometrically valid but chase risk requires a retest")

    if environment.extension_state in {ExtensionState.OVEREXTENDED, ExtensionState.EXTREME}:
        score -= 15.0
        codes.append("ENVIRONMENT_EXTENSION_PENALTY")
        reasons.append("Environment extension reduced near-current entry quality")
    if environment.volatility_state is VolatilityState.EXTREME:
        score -= 10.0
        codes.append("ENVIRONMENT_VOLATILITY_PENALTY")
        reasons.append("Extreme volatility reduced entry quality")

    actionable = state == "READY_NOW" and score >= 55.0 and chase_risk in {
        ChaseRisk.LOW,
        ChaseRisk.MODERATE,
    }
    if actionable:
        codes.append("ENTRY_ACTIONABLE_NOW")
        reasons.append("Entry is near current price with acceptable route and chase risk")

    return NearCurrentEntryDecision(
        entry_state=state,
        actionable_now=actionable,
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
        reason_codes=tuple(dict.fromkeys(codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def near_current_entry_payload(decision: NearCurrentEntryDecision) -> dict[str, object]:
    """Serialize a near-current entry decision."""

    return {
        "entry_state": decision.entry_state,
        "actionable_now": decision.actionable_now,
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
        "chase_risk": decision.chase_risk.value,
        "reason_codes": list(decision.reason_codes),
        "reasons": list(decision.reasons),
    }


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
