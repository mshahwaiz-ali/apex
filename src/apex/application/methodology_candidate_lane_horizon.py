"""Derive measurable lane and holding-horizon inputs from real candidates.

This adapter is intentionally fail-soft.  It never invents missing timeframe,
ATR, lifecycle, or target-duration measurements.  Callers can preserve the
legacy methodology-context path whenever ``assessment`` is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from apex.application.methodology_lane_horizon import (
    LaneHorizonAssessment,
    LaneHorizonInput,
    LifecycleModel,
    PriceEntryRelation,
    TriggerState,
    classify_lane_and_horizon,
)
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.strategies.entry_status import EntryStatus

_TIMEFRAME_SUFFIX_MINUTES: Final[dict[str, float]] = {
    "m": 1.0,
    "h": 60.0,
    "d": 1_440.0,
}


@dataclass(frozen=True, slots=True)
class CandidateLaneHorizonMeasurement:
    """Result of candidate measurement without synthetic defaults."""

    assessment: LaneHorizonAssessment | None
    missing_measurements: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return self.assessment is not None


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if numeric > 0.0 else None


def _positive_int(value: object) -> int | None:
    numeric = _positive_number(value)
    if numeric is None or not numeric.is_integer():
        return None
    return int(numeric)


def _timeframe_minutes(value: object) -> int | None:
    direct = _positive_int(value)
    if direct is not None:
        return direct
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if len(normalized) < 2:
        return None
    suffix = normalized[-1]
    multiplier = _TIMEFRAME_SUFFIX_MINUTES.get(suffix)
    if multiplier is None:
        return None
    try:
        amount = float(normalized[:-1])
    except ValueError:
        return None
    minutes = amount * multiplier
    if minutes <= 0.0 or not minutes.is_integer():
        return None
    return int(minutes)


def _metadata_timeframe(
    candidate: TradeCandidate,
    *keys: str,
) -> int | None:
    for key in keys:
        parsed = _timeframe_minutes(candidate.metadata.get(key))
        if parsed is not None:
            return parsed
    return None


def _price_entry_relation(candidate: TradeCandidate) -> PriceEntryRelation:
    entry = candidate.entry
    current = entry.current_price
    if entry.lower <= current <= entry.upper:
        return PriceEntryRelation.INSIDE_ZONE

    maximum_chase = entry.max_chase_price
    if maximum_chase is not None:
        beyond = (
            current > maximum_chase
            if candidate.direction is TradeDirection.LONG
            else current < maximum_chase
        )
        if beyond:
            return PriceEntryRelation.BEYOND_MAX_CHASE

    return (
        PriceEntryRelation.NEAR_ZONE
        if entry.atr_distance <= 1.0
        else PriceEntryRelation.AWAY_FROM_ZONE
    )


def _trigger_state(entry_status: EntryStatus) -> TriggerState:
    if entry_status in {EntryStatus.READY_NOW, EntryStatus.AGGRESSIVE_NOW}:
        return TriggerState.READY
    if entry_status is EntryStatus.PULLBACK_PREFERRED:
        return TriggerState.PULLBACK_REQUIRED
    if entry_status is EntryStatus.WATCH_NEAR_ENTRY:
        return TriggerState.CONFIRMATION_REQUIRED
    if entry_status is EntryStatus.INVALIDATED:
        return TriggerState.INVALID
    return TriggerState.DEVELOPING


def _lifecycle_model(candidate: TradeCandidate) -> LifecycleModel | None:
    raw = candidate.metadata.get("lifecycle_model")
    if not isinstance(raw, str):
        return None
    try:
        return LifecycleModel(raw.strip().lower())
    except ValueError:
        return None


def measure_candidate_lane_horizon(
    candidate: TradeCandidate,
    *,
    entry_status: EntryStatus,
    runner_authority: bool | None = None,
) -> CandidateLaneHorizonMeasurement:
    """Measure a candidate for the opt-in lane/horizon classifier.

    Missing required inputs produce an unavailable result so callers can use
    the existing legacy inference path.  Candidate expiry bars are deliberately
    not reused as expected bars to target because those values have different
    meanings.
    """

    execution_timeframe = _metadata_timeframe(
        candidate,
        "execution_timeframe",
        "decision_timeframe",
        "confirmation_timeframe",
    )
    setup_timeframe = _metadata_timeframe(
        candidate,
        "setup_timeframe",
        "decision_timeframe",
    )
    invalidation_timeframe = _metadata_timeframe(
        candidate,
        "invalidation_timeframe",
        "setup_timeframe",
    )
    target_timeframe = _metadata_timeframe(
        candidate,
        "target_timeframe",
        "setup_timeframe",
    )
    expected_bars = _positive_int(candidate.metadata.get("expected_bars_to_target"))
    atr = _positive_number(candidate.metadata.get("decision_atr"))
    lifecycle_model = _lifecycle_model(candidate)

    missing: list[str] = []
    for name, value in (
        ("execution_timeframe", execution_timeframe),
        ("setup_timeframe", setup_timeframe),
        ("invalidation_timeframe", invalidation_timeframe),
        ("target_timeframe", target_timeframe),
        ("expected_bars_to_target", expected_bars),
        ("decision_atr", atr),
        ("lifecycle_model", lifecycle_model),
    ):
        if value is None:
            missing.append(name)

    effective_runner_authority = False
    if lifecycle_model is LifecycleModel.RUNNER:
        if runner_authority is None:
            missing.append("runner_authority")
        else:
            effective_runner_authority = runner_authority

    if missing:
        unique_missing = tuple(dict.fromkeys(missing))
        return CandidateLaneHorizonMeasurement(
            assessment=None,
            missing_measurements=unique_missing,
            reasons=(
                "measurable lane/horizon assessment unavailable; "
                "preserve legacy methodology-context inference",
            ),
        )

    assert execution_timeframe is not None
    assert setup_timeframe is not None
    assert invalidation_timeframe is not None
    assert target_timeframe is not None
    assert expected_bars is not None
    assert atr is not None
    assert lifecycle_model is not None

    nearest_target = candidate.targets.levels[0].price
    target_distance = abs(nearest_target - candidate.entry.preferred)
    atr_normalized_target_distance = target_distance / atr
    if atr_normalized_target_distance <= 0.0:
        return CandidateLaneHorizonMeasurement(
            assessment=None,
            missing_measurements=("positive_atr_normalized_target_distance",),
            reasons=(
                "nearest target does not provide a positive ATR-normalized distance; "
                "preserve legacy methodology-context inference",
            ),
        )

    assessment = classify_lane_and_horizon(
        LaneHorizonInput(
            strategy=candidate.strategy,
            execution_timeframe_minutes=execution_timeframe,
            setup_timeframe_minutes=setup_timeframe,
            invalidation_timeframe_minutes=invalidation_timeframe,
            target_timeframe_minutes=target_timeframe,
            atr_normalized_target_distance=atr_normalized_target_distance,
            expected_bars_to_target=expected_bars,
            price_entry_relation=_price_entry_relation(candidate),
            trigger_state=_trigger_state(entry_status),
            lifecycle_model=lifecycle_model,
            runner_authority=effective_runner_authority,
        )
    )
    return CandidateLaneHorizonMeasurement(
        assessment=assessment,
        missing_measurements=(),
        reasons=(
            "lane and holding horizon derived from candidate geometry, "
            "timeframes, ATR target distance, trigger state, and lifecycle",
        ),
    )


__all__ = [
    "CandidateLaneHorizonMeasurement",
    "measure_candidate_lane_horizon",
]
