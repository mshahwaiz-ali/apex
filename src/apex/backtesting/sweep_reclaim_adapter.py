"""Backtest adapter for the shared sweep/reclaim evaluator.

The adapter preserves existing diagnostic metadata names while delegating path
classification to the provider-independent domain evaluator.  It does not alter
trade outcomes or production authority.
"""

from __future__ import annotations

from collections.abc import Sequence

from apex.backtesting.contracts import BacktestSignal
from apex.domain.models import Candle
from apex.domain.sweep_reclaim import (
    DEFAULT_SWEEP_RECLAIM_POLICY,
    SweepReclaimAssessment,
    SweepReclaimPolicy,
    SweepReclaimState,
    evaluate_sweep_reclaim,
)


def assess_post_stop_sweep_reclaim(
    signal: BacktestSignal,
    *,
    entry_price: float,
    stop_price: float,
    stop_candle: Candle,
    confirmation_candles: Sequence[Candle],
    policy: SweepReclaimPolicy = DEFAULT_SWEEP_RECLAIM_POLICY,
) -> SweepReclaimAssessment:
    """Return the shared assessment for one stopped backtest signal."""

    return evaluate_sweep_reclaim(
        direction=signal.direction,
        entry_price=entry_price,
        invalidation_price=stop_price,
        target_price=signal.target_price,
        sweep_candle=stop_candle,
        confirmation_candles=confirmation_candles,
        policy=policy,
    )


def sweep_reclaim_metadata(
    assessment: SweepReclaimAssessment,
) -> dict[str, str | int | float | bool]:
    """Map the shared assessment to legacy backtest diagnostic fields."""

    bars_to_stop_reclaim = assessment.bars_to_invalidation_reclaim
    bars_to_entry_reclaim = assessment.bars_to_entry_reclaim
    reclaim_entry_price = assessment.reclaim_entry_price
    reclaim_candle_index = assessment.reclaim_candle_index

    return {
        "post_stop_maximum_excursion_beyond_stop_r": assessment.maximum_breach_r,
        "post_stop_maximum_close_beyond_stop_r": assessment.maximum_close_breach_r,
        "post_stop_bars_closed_beyond_stop": assessment.bars_closed_beyond_invalidation,
        "post_stop_max_consecutive_closes_beyond_stop": (
            assessment.maximum_consecutive_closes_beyond_invalidation
        ),
        "post_stop_stop_reclaimed": bars_to_stop_reclaim is not None,
        "post_stop_bars_to_stop_reclaim": bars_to_stop_reclaim or 0,
        "post_stop_entry_reclaimed": bars_to_entry_reclaim is not None,
        "post_stop_bars_to_reclaim": bars_to_entry_reclaim or 0,
        "shallow_stop_sweep": assessment.shallow_sweep,
        "wick_only_stop_sweep": assessment.wick_only_sweep,
        "deep_directional_failure": assessment.deep_failure,
        "sweep_reclaim_candidate": assessment.state
        in {
            SweepReclaimState.SHALLOW_SWEEP_PENDING,
            SweepReclaimState.RECLAIM_CONFIRMED,
            SweepReclaimState.RETEST_CONFIRMED,
        },
        "sweep_reclaim_confirmed": assessment.reclaim_confirmed,
        "sweep_reclaim_rejected_reason": assessment.rejected_reason,
        "reclaim_candle_body_ratio": assessment.reclaim_body_ratio,
        "reclaim_close_location": assessment.reclaim_close_location,
        "entry_level_reclaimed": bars_to_entry_reclaim is not None,
        "retest_held": assessment.retest_confirmed,
        "remaining_target_room_r": assessment.remaining_target_room_r,
        "recovery_entry_authorized": assessment.recovery_entry_authorized,
        "recovery_entry_price": reclaim_entry_price or 0.0,
        "recovery_entry_candle": reclaim_candle_index or 0,
        "shared_sweep_reclaim_state": assessment.state.value,
    }
