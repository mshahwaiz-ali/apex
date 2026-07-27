"""Point-in-time quality-recovery contracts and observe-only market profiling."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from statistics import fmean, median
from typing import Any

from apex.application.methodology_geometry_runtime import GeometryExecutionCosts
from apex.domain.decision_volatility import (
    DecisionVolatilityClass,
    build_decision_volatility_profile,
)
from apex.strategies.context import StrategyContext


class ParameterProvenance(StrEnum):
    EXISTING_PRODUCTION_VALUE = "existing_production_value"
    SOURCE_DEFINED_VALUE = "source_defined_value"
    EMPIRICAL_CANDIDATE = "empirical_candidate"
    DERIVED_FROM_TRAINING_DATA = "derived_from_training_data"
    PROMOTED_AFTER_OUT_OF_SAMPLE_VALIDATION = "promoted_after_out_of_sample_validation"


@dataclass(frozen=True, slots=True)
class ResolvedParameter:
    name: str
    base_value: object
    adjustment_factors: tuple[str, ...]
    final_value: object
    units: str
    provenance: ParameterProvenance
    bounds: tuple[float | None, float | None] | None
    version: str
    reason: str

    def __post_init__(self) -> None:
        for name, value in (
            ("name", self.name),
            ("units", self.units),
            ("version", self.version),
            ("reason", self.reason),
        ):
            if not value.strip():
                raise ValueError(f"resolved parameter {name} cannot be empty")
        if self.bounds is not None:
            lower, upper = self.bounds
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("resolved parameter lower bound cannot exceed upper bound")

    def as_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload


@dataclass(frozen=True, slots=True)
class TimeframeSnapshot:
    timeframe: str
    role: str
    closed_candle_count: int
    latest_closed_at: datetime
    active_candle_present: bool
    stale: bool
    staleness_seconds: float
    tick_size: float | None
    step_size: float | None
    minimum_notional: float | None
    future_closed_candle_count: int = 0

    def __post_init__(self) -> None:
        if not self.timeframe.strip() or not self.role.strip():
            raise ValueError("snapshot timeframe and role cannot be empty")
        if self.closed_candle_count < 1:
            raise ValueError("snapshot requires at least one closed candle")
        if self.latest_closed_at.tzinfo is None or self.latest_closed_at.utcoffset() is None:
            raise ValueError("snapshot close time must be timezone-aware")
        if not math.isfinite(self.staleness_seconds) or self.staleness_seconds < 0.0:
            raise ValueError("snapshot staleness must be finite and non-negative")
        if self.future_closed_candle_count < 0:
            raise ValueError("future closed candle count cannot be negative")


@dataclass(frozen=True, slots=True)
class CanonicalMarketSnapshot:
    symbol: str
    decision_time: datetime
    provider: str
    timeframes: tuple[TimeframeSnapshot, ...]
    available_evidence: tuple[str, ...]
    missing_evidence: tuple[tuple[str, str], ...]
    execution_cost_profile: tuple[tuple[str, float | bool], ...]
    authority: str = "observe_only"
    contract_status: str | None = None
    listing_age_days: float | None = None
    precision_valid: bool = False
    quality_status: str = "degraded"
    quality_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.provider.strip():
            raise ValueError("market snapshot symbol and provider cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("market snapshot decision time must be timezone-aware")
        if not self.timeframes:
            raise ValueError("market snapshot requires timeframe observations")
        if any(frame.latest_closed_at > self.decision_time for frame in self.timeframes):
            raise ValueError("market snapshot cannot include a future closed candle")
        if len({frame.timeframe for frame in self.timeframes}) != len(self.timeframes):
            raise ValueError("market snapshot timeframes must be unique")
        if self.contract_status is not None and not self.contract_status.strip():
            raise ValueError("snapshot contract status cannot be blank")
        if self.listing_age_days is not None and (
            not math.isfinite(self.listing_age_days) or self.listing_age_days < 0.0
        ):
            raise ValueError("snapshot listing age must be finite and non-negative")
        if self.quality_status not in {"valid", "degraded", "rejected"}:
            raise ValueError("snapshot quality status must be valid, degraded, or rejected")

    @property
    def snapshot_id(self) -> str:
        payload = canonical_market_snapshot_payload(self, include_id=False)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class MarketBehaviorProfile:
    cohort: str
    liquidity_quote_volume_median: float | None
    volatility_class: str
    volatility_percentile: float | None
    directional_efficiency: float | None
    chop_score: float | None
    wick_noise_score: float | None
    sample_size: int
    false_break_frequency: float | None = None
    execution_friction_score: float | None = None
    listing_maturity_days: float | None = None
    authority: str = "observe_only"
    provenance: ParameterProvenance = ParameterProvenance.EMPIRICAL_CANDIDATE

    def __post_init__(self) -> None:
        if not self.cohort.strip() or self.sample_size < 0:
            raise ValueError("market profile cohort and sample size must be valid")
        for name in (
            "directional_efficiency",
            "chop_score",
            "wick_noise_score",
            "false_break_frequency",
            "execution_friction_score",
        ):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or not 0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between zero and one")
        if self.listing_maturity_days is not None and (
            not math.isfinite(self.listing_maturity_days) or self.listing_maturity_days < 0.0
        ):
            raise ValueError("listing maturity days must be finite and non-negative")


def build_canonical_market_snapshot(
    context: StrategyContext,
    *,
    decision_time: datetime,
    provider: str,
    execution_costs: GeometryExecutionCosts | None,
) -> CanonicalMarketSnapshot:
    """Freeze lineage already consumed by the canonical strategy context."""

    observations: list[TimeframeSnapshot] = []
    for frame in context.frames:
        closed = tuple(
            candle
            for candle in frame.recent_candles
            if candle.is_closed and candle.close_time <= decision_time
        )
        if not closed or frame.last_closed_at is None:
            raise ValueError(f"{context.symbol} {frame.timeframe} has no decision-time closed data")
        all_closed = tuple(candle for candle in frame.recent_candles if candle.is_closed)
        observations.append(
            TimeframeSnapshot(
                timeframe=frame.timeframe,
                role=frame.role.value,
                closed_candle_count=len(closed),
                latest_closed_at=closed[-1].close_time,
                active_candle_present=frame.active_candle,
                stale=frame.is_stale,
                staleness_seconds=frame.staleness_seconds or 0.0,
                tick_size=frame.exchange_tick_size,
                step_size=frame.exchange_step_size,
                minimum_notional=frame.exchange_min_notional,
                future_closed_candle_count=len(all_closed) - len(closed),
            )
        )
    evidence = context.market_evidence
    costs: tuple[tuple[str, float | bool], ...] = ()
    if execution_costs is not None:
        costs = (
            ("entry_fee_pct", execution_costs.entry_fee_pct),
            ("exit_fee_pct", execution_costs.exit_fee_pct),
            ("entry_slippage_pct", execution_costs.entry_slippage_pct),
            ("exit_slippage_pct", execution_costs.exit_slippage_pct),
            (
                "include_observed_spread_in_cost",
                execution_costs.include_observed_spread_in_cost,
            ),
        )
    future_closed = sum(item.future_closed_candle_count for item in observations)
    exchange_filters = None if evidence is None else evidence.exchange_filters
    contract_status = None if exchange_filters is None else exchange_filters.contract_status
    onboarded_at = None if exchange_filters is None else exchange_filters.onboarded_at
    listing_age_days = (
        None
        if onboarded_at is None or onboarded_at > decision_time
        else (decision_time - onboarded_at).total_seconds() / 86_400.0
    )
    quality_reasons: list[str] = []
    if future_closed:
        quality_reasons.append("future_closed_candles_present")
    if any(item.stale for item in observations):
        quality_reasons.append("stale_timeframe")
    if any(item.active_candle_present for item in observations):
        quality_reasons.append("active_candle_present_but_not_authoritative")
    precision_valid = all(
        item.tick_size is not None
        and item.tick_size > 0.0
        and item.step_size is not None
        and item.step_size > 0.0
        for item in observations
    )
    if not precision_valid:
        quality_reasons.append("precision_filters_unavailable_or_invalid")
    if contract_status is None:
        quality_reasons.append("contract_status_unavailable")
    elif contract_status != "TRADING":
        quality_reasons.append("contract_not_trading")
    if listing_age_days is None:
        quality_reasons.append("listing_age_unavailable")
    quality_status = (
        "rejected"
        if future_closed or contract_status not in {None, "TRADING"}
        else ("degraded" if quality_reasons else "valid")
    )
    return CanonicalMarketSnapshot(
        symbol=context.symbol,
        decision_time=decision_time,
        provider=provider,
        timeframes=tuple(observations),
        available_evidence=() if evidence is None else evidence.available_inputs,
        missing_evidence=(
            (("futures_evidence", "disabled_or_unavailable"),)
            if evidence is None
            else evidence.missing_reasons
        ),
        execution_cost_profile=costs,
        precision_valid=precision_valid,
        quality_status=quality_status,
        quality_reasons=tuple(quality_reasons),
        contract_status=contract_status,
        listing_age_days=listing_age_days,
    )


def build_market_behavior_profile(
    context: StrategyContext, *, decision_time: datetime
) -> MarketBehaviorProfile:
    """Build symbol-relative observe-only behavior diagnostics without name rules."""

    candles = tuple(
        candle
        for candle in context.decision_frame.recent_candles
        if candle.is_closed and candle.close_time <= decision_time
    )
    volatility = build_decision_volatility_profile(candles, decision_time=decision_time)
    window = candles[-min(120, len(candles)) :]
    quote_volumes = tuple(
        float(candle.quote_volume)
        for candle in window
        if candle.quote_volume is not None and math.isfinite(candle.quote_volume)
    )
    directional_efficiency: float | None = None
    wick_noise: float | None = None
    false_break_frequency: float | None = None
    if len(window) >= 2:
        path = sum(abs(current.close - previous.close) for previous, current in pairwise(window))
        directional_efficiency = (
            min(1.0, abs(window[-1].close - window[0].close) / path) if path > 0.0 else 0.0
        )
        wick_ratios = tuple(
            max(
                0.0,
                (candle.high - candle.low - abs(candle.close - candle.open))
                / (candle.high - candle.low),
            )
            for candle in window
            if candle.high > candle.low
        )
        wick_noise = fmean(wick_ratios) if wick_ratios else None
        false_break_frequency = _false_break_frequency(window)
    cohort = _behavior_cohort(
        sample_size=len(window),
        volatility_class=volatility.volatility_class,
        efficiency=directional_efficiency,
        wick_noise=wick_noise,
    )
    return MarketBehaviorProfile(
        cohort=cohort,
        liquidity_quote_volume_median=median(quote_volumes) if quote_volumes else None,
        volatility_class=volatility.volatility_class.value,
        volatility_percentile=volatility.percentile,
        directional_efficiency=directional_efficiency,
        chop_score=None if directional_efficiency is None else 1.0 - directional_efficiency,
        wick_noise_score=wick_noise,
        sample_size=len(window),
        false_break_frequency=false_break_frequency,
        execution_friction_score=_execution_friction_score(context),
        listing_maturity_days=_listing_maturity_days(context, decision_time),
    )


def _false_break_frequency(candles: tuple[Any, ...], *, lookback: int = 20) -> float | None:
    if len(candles) <= lookback:
        return None
    tests = 0
    false_breaks = 0
    for index in range(lookback, len(candles)):
        prior = candles[index - lookback : index]
        prior_high = max(item.high for item in prior)
        prior_low = min(item.low for item in prior)
        candle = candles[index]
        broke_high = candle.high > prior_high
        broke_low = candle.low < prior_low
        if not broke_high and not broke_low:
            continue
        tests += 1
        if (broke_high and candle.close <= prior_high) or (broke_low and candle.close >= prior_low):
            false_breaks += 1
    return false_breaks / tests if tests else 0.0


def _execution_friction_score(context: StrategyContext) -> float | None:
    frame = context.decision_frame
    spread = (
        frame.order_book_spread_percentage
        if frame.order_book_spread_percentage is not None
        else frame.spread_percentage
    )
    if spread is None or not math.isfinite(spread):
        return None
    return min(1.0, max(0.0, spread / 0.50))


def _listing_maturity_days(
    context: StrategyContext,
    decision_time: datetime,
) -> float | None:
    evidence = context.market_evidence
    filters = None if evidence is None else evidence.exchange_filters
    onboarded_at = None if filters is None else filters.onboarded_at
    if onboarded_at is None or onboarded_at > decision_time:
        return None
    return (decision_time - onboarded_at).total_seconds() / 86_400.0


def _behavior_cohort(
    *,
    sample_size: int,
    volatility_class: DecisionVolatilityClass,
    efficiency: float | None,
    wick_noise: float | None,
) -> str:
    if sample_size < 50 or efficiency is None:
        return "insufficient_history"
    if wick_noise is not None and wick_noise >= 0.65:
        return "high_wick"
    if volatility_class is DecisionVolatilityClass.EXTREME:
        return "extreme_volatility"
    if efficiency >= 0.45:
        return "directional"
    if efficiency <= 0.20:
        return "range_or_chop"
    return "mixed"


def canonical_market_snapshot_payload(
    snapshot: CanonicalMarketSnapshot, *, include_id: bool = True
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": snapshot.symbol,
        "decision_time": snapshot.decision_time.isoformat(),
        "provider": snapshot.provider,
        "authority": snapshot.authority,
        "contract_status": snapshot.contract_status,
        "listing_age_days": snapshot.listing_age_days,
        "precision_valid": snapshot.precision_valid,
        "quality_status": snapshot.quality_status,
        "quality_reasons": list(snapshot.quality_reasons),
        "timeframes": [
            {
                **asdict(frame),
                "latest_closed_at": frame.latest_closed_at.isoformat(),
            }
            for frame in snapshot.timeframes
        ],
        "available_evidence": list(snapshot.available_evidence),
        "missing_evidence": [list(item) for item in snapshot.missing_evidence],
        "execution_cost_profile": dict(snapshot.execution_cost_profile),
    }
    if include_id:
        payload["snapshot_id"] = snapshot.snapshot_id
    return payload


def market_behavior_profile_payload(profile: MarketBehaviorProfile) -> dict[str, object]:
    payload = asdict(profile)
    payload["provenance"] = profile.provenance.value
    return payload


__all__ = [
    "CanonicalMarketSnapshot",
    "MarketBehaviorProfile",
    "ParameterProvenance",
    "ResolvedParameter",
    "TimeframeSnapshot",
    "build_canonical_market_snapshot",
    "build_market_behavior_profile",
    "canonical_market_snapshot_payload",
    "market_behavior_profile_payload",
]
