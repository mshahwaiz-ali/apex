"""Volatility-aware, decision-time risk diagnostics for backtest shadow analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.backtesting.contracts import BacktestSignal


class VolatilityClass(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VolatilityRiskAssessment:
    volatility_class: VolatilityClass
    atr_percent: float | None
    stop_atr_ratio: float | None
    risk_score: float
    reasons: tuple[str, ...]
    elevated: bool
    authority: str = "observe_only"


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        result = float(value)
        if math.isfinite(result):
            return result
    return None


def _diagnostic(signal: BacktestSignal, *keys: str) -> float | None:
    for key in keys:
        value = _number(signal.diagnostics.get(key))
        if value is not None:
            return value
    return None


def _atr_percent(signal: BacktestSignal) -> float | None:
    atr = _diagnostic(signal, "decision_atr", "atr", "execution_atr")
    if atr is None or signal.entry_price <= 0:
        return None
    return atr / signal.entry_price * 100.0


def _stop_atr_ratio(signal: BacktestSignal) -> float | None:
    atr = _diagnostic(signal, "decision_atr", "atr", "execution_atr")
    stop_distance = _diagnostic(signal, "stop_distance")
    if stop_distance is None:
        stop_distance = abs(signal.entry_price - signal.stop_price)
    if atr is None or atr <= 0:
        return None
    return stop_distance / atr


def classify_volatility(signal: BacktestSignal) -> VolatilityClass:
    """Classify the current decision using normalized ATR percentage only."""

    atr_percent = _atr_percent(signal)
    if atr_percent is None:
        return VolatilityClass.UNKNOWN
    if atr_percent < 0.35:
        return VolatilityClass.LOW
    if atr_percent < 0.90:
        return VolatilityClass.NORMAL
    return VolatilityClass.HIGH


def assess_volatility_risk(signal: BacktestSignal) -> VolatilityRiskAssessment:
    """Evaluate volatility-specific failure risk without changing execution authority."""

    volatility_class = classify_volatility(signal)
    atr_percent = _atr_percent(signal)
    stop_atr_ratio = _stop_atr_ratio(signal)
    gross_r = _diagnostic(signal, "gross_tp1_r")
    expected_bars = _diagnostic(signal, "expected_bars_to_target")
    final_score = _diagnostic(signal, "final_score", "final_rank_score")
    momentum = _diagnostic(signal, "momentum_alignment")
    target_quality = _diagnostic(signal, "target_quality")

    score = 0.0
    reasons: list[str] = []

    if volatility_class is VolatilityClass.HIGH:
        if gross_r is not None and gross_r >= 1.75:
            score += 30.0
            reasons.append("high_volatility_inflated_gross_r")
        if final_score is not None and final_score <= 60.87:
            score += 20.0
            reasons.append("high_volatility_weak_final_score")
        if momentum is not None and momentum <= 58.44:
            score += 20.0
            reasons.append("high_volatility_weak_momentum")
        if stop_atr_ratio is not None and stop_atr_ratio < 0.75:
            score += 20.0
            reasons.append("high_volatility_stop_inside_noise")

    elif volatility_class is VolatilityClass.LOW:
        if stop_atr_ratio is not None and stop_atr_ratio < 0.90:
            score += 30.0
            reasons.append("low_volatility_stop_inside_noise")
        if expected_bars is not None and expected_bars >= 4.0:
            score += 20.0
            reasons.append("low_volatility_slow_target_horizon")
        if target_quality is not None and target_quality <= 85.0:
            score += 20.0
            reasons.append("low_volatility_weak_target_quality")
        if gross_r is not None and gross_r >= 2.50:
            score += 15.0
            reasons.append("low_volatility_artificial_reward_ratio")
        if momentum is not None and momentum <= 55.0:
            score += 15.0
            reasons.append("low_volatility_weak_momentum")

    elif volatility_class is VolatilityClass.NORMAL:
        if gross_r is not None and gross_r >= 2.10:
            score += 25.0
            reasons.append("normal_volatility_elevated_gross_r")
        if target_quality is not None and target_quality <= 85.0:
            score += 20.0
            reasons.append("normal_volatility_weak_target_quality")
        if expected_bars is not None and expected_bars >= 3.0:
            score += 15.0
            reasons.append("normal_volatility_slow_target_horizon")
        if stop_atr_ratio is not None and stop_atr_ratio < 0.80:
            score += 25.0
            reasons.append("normal_volatility_stop_inside_noise")
        if momentum is not None and momentum <= 58.0:
            score += 15.0
            reasons.append("normal_volatility_weak_momentum")

    else:
        reasons.append("volatility_context_unavailable")

    return VolatilityRiskAssessment(
        volatility_class=volatility_class,
        atr_percent=atr_percent,
        stop_atr_ratio=stop_atr_ratio,
        risk_score=min(100.0, score),
        reasons=tuple(reasons),
        elevated=score >= 50.0,
    )


def volatility_risk_shadow_metadata(signal: BacktestSignal) -> dict[str, str | int | float | bool]:
    """Expose the assessment for analysis while preserving production behavior."""

    assessment = assess_volatility_risk(signal)
    return {
        "volatility_risk_authority": assessment.authority,
        "volatility_class": assessment.volatility_class.value,
        "volatility_atr_percent": assessment.atr_percent or 0.0,
        "volatility_stop_atr_ratio": assessment.stop_atr_ratio or 0.0,
        "volatility_risk_score": assessment.risk_score,
        "volatility_risk_reasons": ",".join(assessment.reasons),
        "volatility_risk_elevated": assessment.elevated,
        "volatility_risk_would_block": False,
    }
