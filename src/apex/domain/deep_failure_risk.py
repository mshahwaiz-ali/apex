"""Pre-entry deep-failure risk assessment.

This module is deliberately shadow-only. It uses information available on the
signal at decision time and never consumes future candles or post-trade facts.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from apex.backtesting.contracts import BacktestSignal


class FailureRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass(frozen=True, slots=True)
class DeepFailureRiskAssessment:
    score: float
    level: FailureRiskLevel
    reasons: tuple[str, ...]
    would_block: bool
    opposite_review_required: bool


def _number(mapping: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float) and math.isfinite(float(value)):
            return float(value)
    return None


def _truthy(mapping: Mapping[str, object], *keys: str) -> bool:
    for key in keys:
        value = mapping.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().lower() in {
            "true",
            "yes",
            "strong",
            "severe",
            "opposite",
            "contradiction",
            "blocked",
        }:
            return True
    return False


def _text(mapping: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def assess_deep_failure_risk(signal: BacktestSignal) -> DeepFailureRiskAssessment:
    """Assess pre-entry failure risk without changing execution authority."""

    diagnostics = signal.diagnostics
    score = 0.0
    reasons: list[str] = []

    risk_distance = abs(signal.entry_price - signal.stop_price)
    reward_distance = abs(signal.target_price - signal.entry_price)
    gross_rr = reward_distance / risk_distance if risk_distance > 0.0 else 0.0

    htf_conflict = _truthy(
        diagnostics,
        "higher_timeframe_contradiction",
        "htf_contradiction",
        "opposite_continuation_conflict",
        "directional_parent_conflict",
    )
    htf_alignment = _text(
        diagnostics,
        "higher_timeframe_alignment",
        "htf_alignment",
        "trend_alignment",
    )
    if htf_conflict or htf_alignment in {"against", "opposite", "conflict", "contradiction"}:
        score += 34.0
        reasons.append("higher_timeframe_directional_conflict")

    target_room_r = _number(
        diagnostics,
        "remaining_target_room_r",
        "net_target_room_r",
        "target_room_r",
        "net_reward_r",
    )
    if target_room_r is not None and target_room_r < 1.0:
        score += 22.0
        reasons.append("insufficient_remaining_target_room")
    elif gross_rr < 1.0:
        score += 18.0
        reasons.append("weak_gross_reward_to_risk")

    setup_maturity = _text(
        diagnostics,
        "setup_maturity",
        "continuation_maturity",
        "move_maturity",
    )
    if setup_maturity in {"mature", "late", "exhausted", "overextended", "chased"}:
        score += 18.0
        reasons.append("late_or_mature_setup")

    if _truthy(
        diagnostics,
        "maximum_chase_breached",
        "entry_chased",
        "overextended_from_structure",
        "excessive_vwap_distance",
        "excessive_ema_distance",
    ):
        score += 18.0
        reasons.append("entry_location_overextended")

    breakout_quality = _number(
        diagnostics,
        "breakout_quality_score",
        "breakout_acceptance_score",
        "confirmation_quality_score",
    )
    if breakout_quality is not None and breakout_quality < 45.0:
        score += 16.0
        reasons.append("weak_breakout_acceptance")

    body_ratio = _number(
        diagnostics,
        "trigger_body_ratio",
        "breakout_body_ratio",
        "confirmation_body_ratio",
    )
    if body_ratio is not None and body_ratio < 0.35:
        score += 12.0
        reasons.append("weak_confirmation_body")

    location = _text(
        diagnostics,
        "entry_location_quality",
        "structure_location",
        "location_quality",
    )
    if location in {
        "poor",
        "range_midpoint",
        "into_resistance",
        "into_support",
        "opposing_liquidity",
    }:
        score += 18.0
        reasons.append("poor_structural_location")

    regime_fit = _text(
        diagnostics,
        "strategy_regime_fit",
        "regime_fit",
        "methodology_fit",
    )
    if regime_fit in {"poor", "invalid", "mismatch", "not_declared", "suppressed"}:
        score += 24.0
        reasons.append("strategy_regime_mismatch")

    if signal.confidence_score < 45.0:
        score += 10.0
        reasons.append("low_setup_confidence")

    if signal.setup_validity.strip().lower() not in {"valid", "confirmed"}:
        score += 18.0
        reasons.append("setup_not_fully_valid")

    score = min(100.0, score)
    if score >= 70.0:
        level = FailureRiskLevel.EXTREME
    elif score >= 45.0:
        level = FailureRiskLevel.HIGH
    elif score >= 20.0:
        level = FailureRiskLevel.MODERATE
    else:
        level = FailureRiskLevel.LOW

    would_block = level is FailureRiskLevel.EXTREME
    opposite_review_required = htf_conflict and level in {
        FailureRiskLevel.HIGH,
        FailureRiskLevel.EXTREME,
    }
    return DeepFailureRiskAssessment(
        score=score,
        level=level,
        reasons=tuple(reasons),
        would_block=would_block,
        opposite_review_required=opposite_review_required,
    )


def deep_failure_shadow_metadata(
    signal: BacktestSignal,
) -> dict[str, str | int | float | bool]:
    """Expose identity and shadow risk facts in deterministic replay metadata."""

    assessment = assess_deep_failure_risk(signal)
    return {
        "signal_symbol": signal.symbol,
        "signal_strategy": signal.strategy.value,
        "signal_direction": signal.direction.value,
        "signal_generated_at": signal.generated_at.isoformat(),
        "signal_entry_price": signal.entry_price,
        "signal_stop_price": signal.stop_price,
        "signal_target_price": signal.target_price,
        "signal_confidence_score": signal.confidence_score,
        "deep_failure_shadow_score": assessment.score,
        "deep_failure_shadow_level": assessment.level.value,
        "deep_failure_shadow_reasons": ",".join(assessment.reasons),
        "deep_failure_shadow_would_block": assessment.would_block,
        "deep_failure_shadow_opposite_review_required": (
            assessment.opposite_review_required
        ),
        "deep_failure_shadow_authority": "observe_only",
    }
