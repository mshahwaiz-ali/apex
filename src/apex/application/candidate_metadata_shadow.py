"""Deterministic shadow-only candidate lane and horizon metadata.

This module enriches candidate diagnostics without changing candidate
eligibility, scoring, selection, geometry, or execution authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from apex.strategies import EntryOpportunityHorizon, StrategyType
from apex.strategies.contracts import TradeCandidate


@dataclass(frozen=True, slots=True)
class ShadowTimeframeProfile:
    execution_timeframe: str
    setup_timeframe: str
    invalidation_timeframe: str
    target_timeframe: str
    lifecycle_model: str


_PROFILES: dict[StrategyType, ShadowTimeframeProfile] = {
    StrategyType.MOMENTUM_SCALP: ShadowTimeframeProfile("1m", "3m", "3m", "5m", "scalp"),
    StrategyType.MOMENTUM_BREAKOUT: ShadowTimeframeProfile(
        "3m", "5m", "5m", "15m", "momentum_continuation"
    ),
    StrategyType.BREAKOUT_CONTINUATION: ShadowTimeframeProfile(
        "5m", "15m", "15m", "30m", "continuation"
    ),
    StrategyType.COMPRESSION_EXPANSION: ShadowTimeframeProfile(
        "5m", "15m", "15m", "30m", "expansion"
    ),
    StrategyType.BREAKOUT_RETEST: ShadowTimeframeProfile(
        "5m", "15m", "15m", "30m", "breakout_retest"
    ),
    StrategyType.FIRST_PULLBACK_CONTINUATION: ShadowTimeframeProfile(
        "5m", "15m", "15m", "30m", "first_pullback"
    ),
    StrategyType.TREND_PULLBACK: ShadowTimeframeProfile("5m", "15m", "30m", "1h", "trend_pullback"),
    StrategyType.VWAP_RECLAIM_REJECTION: ShadowTimeframeProfile(
        "3m", "5m", "5m", "15m", "reclaim_rejection"
    ),
    StrategyType.RANGE_REVERSAL: ShadowTimeframeProfile(
        "5m", "15m", "15m", "30m", "range_reversal"
    ),
    StrategyType.FAILED_BREAKOUT_REVERSAL: ShadowTimeframeProfile(
        "3m", "5m", "5m", "15m", "failed_breakout"
    ),
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: ShadowTimeframeProfile(
        "3m", "5m", "5m", "15m", "liquidity_rejection"
    ),
    StrategyType.EXHAUSTION_REVERSAL: ShadowTimeframeProfile(
        "3m", "5m", "5m", "15m", "exhaustion_reversal"
    ),
}

_LANE_FROM_ENTRY_HORIZON = {
    EntryOpportunityHorizon.IMMEDIATE: "immediate_tactical",
    EntryOpportunityHorizon.NEARBY: "nearby_structured",
    EntryOpportunityHorizon.FUTURE_TRIGGER: "intraday_structured",
    EntryOpportunityHorizon.OUTSIDE_HORIZON: "extended_structured",
}


def enrich_candidate_metadata(candidate: TradeCandidate) -> dict[str, Any]:
    """Return shadow metadata while preserving every original metadata value."""

    metadata: dict[str, object] = dict(candidate.metadata)
    profile = _PROFILES[candidate.strategy]

    execution_timeframe = _text(metadata, "execution_timeframe") or profile.execution_timeframe
    setup_timeframe = _text(metadata, "setup_timeframe") or profile.setup_timeframe
    invalidation_timeframe = (
        _text(metadata, "invalidation_timeframe") or profile.invalidation_timeframe
    )
    target_timeframe = _text(metadata, "target_timeframe") or profile.target_timeframe
    lifecycle_model = _text(metadata, "lifecycle_model") or profile.lifecycle_model
    decision_atr = _decision_atr(candidate, metadata)
    expected_bars = _expected_bars_to_target(candidate, decision_atr)

    legacy_lane = (
        _text(metadata, "legacy_context_lane")
        or _text(metadata, "context_lane")
        or _text(metadata, "lane")
        or _LANE_FROM_ENTRY_HORIZON[candidate.entry.horizon]
    )
    measured_lane = _measured_lane(expected_bars)
    legacy_horizon = (
        _text(metadata, "legacy_holding_horizon")
        or _text(metadata, "holding_horizon")
        or _legacy_holding_horizon(legacy_lane)
    )
    measured_horizon = _measured_holding_horizon(
        expected_bars=expected_bars,
        target_timeframe=target_timeframe,
    )

    shadow = {
        "execution_timeframe": execution_timeframe,
        "setup_timeframe": setup_timeframe,
        "invalidation_timeframe": invalidation_timeframe,
        "target_timeframe": target_timeframe,
        "expected_bars_to_target": expected_bars,
        "decision_atr": decision_atr,
        "lifecycle_model": lifecycle_model,
        "legacy_context_lane": legacy_lane,
        "measured_context_lane": measured_lane,
        "legacy_holding_horizon": legacy_horizon,
        "measured_holding_horizon": measured_horizon,
        "would_change_lane": None if measured_lane is None else measured_lane != legacy_lane,
        "would_change_geometry_result": metadata.get("would_change_geometry_result"),
        "shadow_metadata_version": 1,
        "shadow_metadata_authoritative": False,
    }
    for key, value in shadow.items():
        metadata.setdefault(key, value)
    return metadata


def shadow_metadata_from_mapping(
    metadata: Mapping[str, object],
    *,
    entry_horizon: object | None = None,
    strategy: object | None = None,
    entry_price: object | None = None,
    target_price: object | None = None,
) -> dict[str, object]:
    """Normalize or derive shadow metadata for reports and geometry audits."""

    result = dict(metadata)
    strategy_type = _strategy_type(strategy)
    if strategy_type is not None:
        profile = _PROFILES[strategy_type]
        result.setdefault("execution_timeframe", profile.execution_timeframe)
        result.setdefault("setup_timeframe", profile.setup_timeframe)
        result.setdefault("invalidation_timeframe", profile.invalidation_timeframe)
        result.setdefault("target_timeframe", profile.target_timeframe)
        result.setdefault("lifecycle_model", profile.lifecycle_model)

    entry = _positive_number(entry_price)
    target = _positive_number(target_price)
    decision_atr = _positive_number_recursive(
        result,
        (
            "decision_atr",
            "decision_frame_atr",
            "current_atr",
            "atr",
            "atr_value",
        ),
    )
    if decision_atr is None:
        stop_distance = _positive_number_recursive(
            result,
            ("stop_distance", "executable_risk_distance", "risk_distance"),
        )
        stop_distance_atr = _positive_number_recursive(
            result,
            ("stop_distance_atr", "stop_atr_distance", "risk_atr"),
        )
        if stop_distance is None and entry is not None and stop_distance_atr is not None:
            executable_stop = _positive_number_recursive(
                result,
                ("executable_stop", "stop_price", "invalidation_price"),
            )
            if executable_stop is not None:
                stop_distance = abs(entry - executable_stop)
        if stop_distance is not None and stop_distance_atr is not None:
            derived = stop_distance / stop_distance_atr
            if math.isfinite(derived) and derived > 0.0:
                decision_atr = derived
    result.setdefault("decision_atr", decision_atr)

    expected_bars = _positive_int(result.get("expected_bars_to_target"))
    if (
        expected_bars is None
        and decision_atr is not None
        and entry is not None
        and target is not None
    ):
        distance = abs(target - entry)
        if math.isfinite(distance) and distance > 0.0:
            expected_bars = max(1, min(64, math.ceil(distance / decision_atr)))
    result.setdefault("expected_bars_to_target", expected_bars)
    legacy_lane = _text(result, "legacy_context_lane") or _text(result, "context_lane")
    if legacy_lane is None and entry_horizon is not None:
        raw = getattr(entry_horizon, "value", entry_horizon)
        try:
            legacy_lane = _LANE_FROM_ENTRY_HORIZON[EntryOpportunityHorizon(str(raw))]
        except ValueError:
            legacy_lane = None
    measured_lane = _text(result, "measured_context_lane") or _measured_lane(expected_bars)
    result.setdefault("legacy_context_lane", legacy_lane)
    result.setdefault("measured_context_lane", measured_lane)

    legacy_horizon = (
        _text(result, "legacy_holding_horizon")
        or _text(result, "holding_horizon")
        or (_legacy_holding_horizon(legacy_lane) if legacy_lane is not None else None)
    )
    target_timeframe = _text(result, "target_timeframe")
    measured_horizon = _text(result, "measured_holding_horizon") or (
        _measured_holding_horizon(
            expected_bars=expected_bars,
            target_timeframe=target_timeframe,
        )
        if target_timeframe is not None
        else None
    )
    result.setdefault("legacy_holding_horizon", legacy_horizon)
    result.setdefault("measured_holding_horizon", measured_horizon)
    result.setdefault(
        "would_change_lane",
        None if legacy_lane is None or measured_lane is None else legacy_lane != measured_lane,
    )
    lane_changed = (
        None if legacy_lane is None or measured_lane is None else legacy_lane != measured_lane
    )
    result.setdefault("would_change_lane", lane_changed)
    result.setdefault(
        "would_change_geometry_result",
        False if lane_changed is False else None,
    )
    return result


def _decision_atr(candidate: TradeCandidate, metadata: Mapping[str, object]) -> float | None:
    explicit = _positive_number_recursive(
        metadata,
        ("decision_atr", "decision_frame_atr", "current_atr", "atr", "atr_value"),
    )
    if explicit is not None:
        return explicit

    if candidate.entry.atr_distance > 0.0:
        price_distance = abs(candidate.entry.preferred - candidate.entry.current_price)
        derived = price_distance / candidate.entry.atr_distance
        if math.isfinite(derived) and derived > 0.0:
            return derived

    stop_atr = _positive_number_recursive(
        metadata,
        ("stop_distance_atr", "stop_atr_distance", "risk_atr"),
    )
    if stop_atr is not None:
        risk = abs(candidate.entry.preferred - candidate.invalidation.price)
        derived = risk / stop_atr
        if math.isfinite(derived) and derived > 0.0:
            return derived
    return None


def _expected_bars_to_target(candidate: TradeCandidate, decision_atr: float | None) -> int | None:
    if decision_atr is None or decision_atr <= 0.0:
        return None
    first_target = candidate.targets.levels[0].price
    distance = abs(first_target - candidate.entry.preferred)
    if not math.isfinite(distance) or distance <= 0.0:
        return None
    # Price-distance projection only. Never use entry expiry, activation timeout,
    # lifecycle expiry, maximum holding bars, or replay window length here.
    return max(1, min(64, math.ceil(distance / decision_atr)))


def _measured_lane(expected_bars: int | None) -> str | None:
    if expected_bars is None:
        return None
    if expected_bars <= 3:
        return "immediate_tactical"
    if expected_bars <= 8:
        return "nearby_structured"
    if expected_bars <= 20:
        return "intraday_structured"
    return "extended_structured"


def _legacy_holding_horizon(lane: str) -> str:
    return {
        "immediate_tactical": "scalp",
        "nearby_structured": "intraday",
        "intraday_structured": "intraday",
        "extended_structured": "swing",
    }.get(lane, "unavailable")


def _measured_holding_horizon(*, expected_bars: int | None, target_timeframe: str) -> str | None:
    if expected_bars is None:
        return None
    timeframe_minutes = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
    }.get(target_timeframe)
    if timeframe_minutes is None:
        return None
    minutes = expected_bars * timeframe_minutes
    if minutes <= 30:
        return "scalp"
    if minutes <= 360:
        return "intraday"
    return "swing"


def _strategy_type(value: object) -> StrategyType | None:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        return None
    try:
        return StrategyType(raw)
    except ValueError:
        return None


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric > 0.0 else None


def _positive_int(value: object) -> int | None:
    numeric = _positive_number(value)
    if numeric is None:
        return None
    integer = int(numeric)
    return integer if integer > 0 else None


def _text(values: Mapping[str, object], key: str) -> str | None:
    value = values.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _positive_number_recursive(value: object, keys: tuple[str, ...]) -> float | None:
    if isinstance(value, Mapping):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                numeric = float(candidate)
                if math.isfinite(numeric) and numeric > 0.0:
                    return numeric
        for nested in value.values():
            found = _positive_number_recursive(nested, keys)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found = _positive_number_recursive(nested, keys)
            if found is not None:
                return found
    return None


__all__ = [
    "ShadowTimeframeProfile",
    "enrich_candidate_metadata",
    "shadow_metadata_from_mapping",
]
