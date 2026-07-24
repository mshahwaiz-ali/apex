"""Normalize decision-time signal diagnostics for leakage-safe analysis."""

from __future__ import annotations

import math
from collections.abc import Mapping

from apex.backtesting.contracts import BacktestSignal

Scalar = str | int | float | bool

ALIASES: dict[str, tuple[str, ...]] = {
    "decision_15m_trend": ("trend_15m", "setup_timeframe_trend", "fifteen_minute_trend"),
    "decision_30m_trend": ("trend_30m", "directional_parent_trend", "thirty_minute_trend"),
    "decision_1h_trend": ("trend_1h", "one_hour_trend"),
    "decision_4h_trend": ("trend_4h", "four_hour_trend"),
    "decision_htf_conflict_score": (
        "higher_timeframe_contradiction_score",
        "htf_contradiction_score",
        "directional_parent_conflict_score",
    ),
    "decision_htf_conflict": (
        "higher_timeframe_contradiction",
        "htf_contradiction",
        "opposite_continuation_conflict",
        "directional_parent_conflict",
    ),
    "decision_setup_maturity": (
        "setup_maturity",
        "continuation_maturity",
        "move_maturity",
    ),
    "decision_regime_fit": (
        "strategy_regime_fit",
        "regime_fit",
        "methodology_fit",
    ),
    "decision_breakout_body_ratio": (
        "breakout_body_ratio",
        "trigger_body_ratio",
        "confirmation_body_ratio",
    ),
    "decision_rejection_wick_ratio": (
        "rejection_wick_ratio",
        "opposing_wick_ratio",
        "trigger_rejection_wick_ratio",
    ),
    "decision_relative_volume": (
        "relative_volume",
        "relative_volume_ratio",
        "rvol",
    ),
    "decision_ema_distance_atr": (
        "ema_distance_atr",
        "distance_from_ema_atr",
        "ema_extension_atr",
    ),
    "decision_vwap_distance_atr": (
        "vwap_distance_atr",
        "distance_from_vwap_atr",
        "vwap_extension_atr",
    ),
    "decision_target_room_net_r": (
        "remaining_target_room_r",
        "net_target_room_r",
        "target_room_r",
        "net_reward_r",
    ),
    "decision_confirmation_quality": (
        "confirmation_quality_score",
        "breakout_acceptance_score",
        "breakout_quality_score",
    ),
    "decision_location_quality": (
        "entry_location_quality",
        "structure_location",
        "location_quality",
    ),
    "decision_momentum_alignment": (
        "momentum_alignment",
        "momentum_agreement",
        "momentum_state",
    ),
    "decision_market_regime": ("market_regime", "primary_regime", "regime"),
    "decision_setup_family": ("setup_family", "strategy_family"),
}


def _scalar(value: object) -> Scalar | None:
    if isinstance(value, bool | str):
        return value
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return value
    return None


def _first(diagnostics: Mapping[str, object], keys: tuple[str, ...]) -> Scalar | None:
    for key in keys:
        value = _scalar(diagnostics.get(key))
        if value is not None and value != "":
            return value
    return None


def decision_feature_snapshot(signal: BacktestSignal) -> dict[str, Scalar]:
    """Return only facts already attached to the signal at decision time."""

    diagnostics = signal.diagnostics
    snapshot: dict[str, Scalar] = {
        "decision_symbol": signal.symbol,
        "decision_strategy": signal.strategy.value,
        "decision_direction": signal.direction.value,
        "decision_generated_at": signal.generated_at.isoformat(),
        "decision_entry_price": signal.entry_price,
        "decision_stop_price": signal.stop_price,
        "decision_target_price": signal.target_price,
        "decision_confidence_score": signal.confidence_score,
        "decision_setup_validity": signal.setup_validity,
        "decision_execution_authority": signal.execution_authority,
        "decision_activation_type": (
            "none" if signal.activation_type is None else signal.activation_type.value
        ),
    }

    for output_key, aliases in ALIASES.items():
        value = _first(diagnostics, aliases)
        if value is not None:
            snapshot[output_key] = value

    # Preserve every scalar signal diagnostic for discovery without allowing
    # future replay metadata into this namespace.
    for key, raw_value in diagnostics.items():
        value = _scalar(raw_value)
        if value is None:
            continue
        normalized = "".join(char if char.isalnum() else "_" for char in key.lower()).strip("_")
        if not normalized:
            continue
        snapshot.setdefault(f"decision_raw_{normalized}", value)

    snapshot["decision_feature_count"] = len(snapshot)
    return snapshot
