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
    EXTREME = "extreme"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VolatilityContext:
    atr_percent: float | None
    stop_atr_ratio: float | None
    source: str


@dataclass(frozen=True)
class VolatilityRiskAssessment:
    volatility_class: VolatilityClass
    atr_percent: float | None
    stop_atr_ratio: float | None
    source: str
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


def _positive(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return value


def _volatility_context(signal: BacktestSignal) -> VolatilityContext:
    """Resolve ATR percentage from canonical or fallback measurements."""

    stop_distance = abs(signal.entry_price - signal.stop_price)
    profile = signal.decision_volatility_profile
    if profile is not None and profile.available and profile.atr_pct is not None:
        derived_atr = signal.entry_price * profile.atr_pct / 100.0
        return VolatilityContext(
            atr_percent=profile.atr_pct,
            stop_atr_ratio=stop_distance / derived_atr if derived_atr > 0.0 else None,
            source=profile.source,
        )
    target_distance = abs(signal.target_price - signal.entry_price)

    direct_atr = _positive(_diagnostic(signal, "decision_atr", "atr", "execution_atr"))
    if direct_atr is not None and signal.entry_price > 0:
        stop_ratio = _positive(_diagnostic(signal, "stop_distance_atr", "gross_stop_distance_atr"))
        if stop_ratio is None and stop_distance > 0:
            stop_ratio = stop_distance / direct_atr
        return VolatilityContext(
            atr_percent=direct_atr / signal.entry_price * 100.0,
            stop_atr_ratio=stop_ratio,
            source="direct_atr",
        )

    stop_atr_ratio = _positive(_diagnostic(signal, "stop_distance_atr", "gross_stop_distance_atr"))
    stop_distance_pct = _positive(
        _diagnostic(signal, "stop_distance_pct", "gross_stop_distance_pct")
    )
    if stop_distance_pct is None and signal.entry_price > 0 and stop_distance > 0:
        stop_distance_pct = stop_distance / signal.entry_price * 100.0
    if stop_atr_ratio is not None and stop_distance_pct is not None:
        return VolatilityContext(
            atr_percent=stop_distance_pct / stop_atr_ratio,
            stop_atr_ratio=stop_atr_ratio,
            source="derived_from_stop_geometry",
        )

    target_atr_ratio = _positive(
        _diagnostic(
            signal,
            "tp1_distance_atr",
            "available_tp1_distance_atr",
            "target_distance_atr",
        )
    )
    target_distance_pct = _positive(
        _diagnostic(
            signal,
            "tp1_distance_pct",
            "available_tp1_distance_pct",
            "target_distance_pct",
        )
    )
    if target_distance_pct is None and signal.entry_price > 0 and target_distance > 0:
        target_distance_pct = target_distance / signal.entry_price * 100.0
    if target_atr_ratio is not None and target_distance_pct is not None:
        atr_percent = target_distance_pct / target_atr_ratio
        derived_atr = signal.entry_price * atr_percent / 100.0
        derived_stop_ratio = None
        if derived_atr > 0 and stop_distance > 0:
            derived_stop_ratio = stop_distance / derived_atr
        return VolatilityContext(
            atr_percent=atr_percent,
            stop_atr_ratio=derived_stop_ratio,
            source="derived_from_target_geometry",
        )

    return VolatilityContext(
        atr_percent=None,
        stop_atr_ratio=stop_atr_ratio,
        source="unavailable",
    )


def _classify_atr_percent(atr_percent: float | None) -> VolatilityClass:
    if atr_percent is None:
        return VolatilityClass.UNKNOWN
    if atr_percent < 0.35:
        return VolatilityClass.LOW
    if atr_percent < 0.90:
        return VolatilityClass.NORMAL
    return VolatilityClass.HIGH


def classify_volatility(signal: BacktestSignal) -> VolatilityClass:
    """Classify using canonical symbol-relative volatility when available."""

    profile = signal.decision_volatility_profile
    if profile is not None and profile.available:
        return VolatilityClass(profile.volatility_class.value)
    return _classify_atr_percent(_volatility_context(signal).atr_percent)


def assess_volatility_risk(signal: BacktestSignal) -> VolatilityRiskAssessment:
    """Evaluate volatility-specific failure risk without changing execution authority."""

    context = _volatility_context(signal)
    profile = signal.decision_volatility_profile
    volatility_class = (
        VolatilityClass(profile.volatility_class.value)
        if profile is not None and profile.available
        else _classify_atr_percent(context.atr_percent)
    )
    gross_r = _diagnostic(signal, "gross_tp1_r")
    expected_bars = _diagnostic(signal, "expected_bars_to_target")
    final_score = _diagnostic(signal, "final_score", "final_rank_score")
    momentum = _diagnostic(signal, "momentum_alignment")
    target_quality = _diagnostic(signal, "target_quality")

    score = 0.0
    reasons: list[str] = []

    if volatility_class in {VolatilityClass.HIGH, VolatilityClass.EXTREME}:
        if gross_r is not None and gross_r >= 1.75:
            score += 30.0
            reasons.append("high_volatility_inflated_gross_r")
        if final_score is not None and final_score <= 60.87:
            score += 20.0
            reasons.append("high_volatility_weak_final_score")
        if momentum is not None and momentum <= 58.44:
            score += 20.0
            reasons.append("high_volatility_weak_momentum")
        if context.stop_atr_ratio is not None and context.stop_atr_ratio < 0.75:
            score += 20.0
            reasons.append("high_volatility_stop_inside_noise")

    elif volatility_class is VolatilityClass.LOW:
        if context.stop_atr_ratio is not None and context.stop_atr_ratio < 0.90:
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
        if context.stop_atr_ratio is not None and context.stop_atr_ratio < 0.80:
            score += 25.0
            reasons.append("normal_volatility_stop_inside_noise")
        if momentum is not None and momentum <= 58.0:
            score += 15.0
            reasons.append("normal_volatility_weak_momentum")

    else:
        reasons.append("volatility_context_unavailable")

    return VolatilityRiskAssessment(
        volatility_class=volatility_class,
        atr_percent=context.atr_percent,
        stop_atr_ratio=context.stop_atr_ratio,
        source=context.source,
        risk_score=min(100.0, score),
        reasons=tuple(reasons),
        elevated=score >= 50.0,
    )


def volatility_risk_shadow_metadata(signal: BacktestSignal) -> dict[str, str | int | float | bool]:
    """Expose the assessment for analysis while preserving production behavior."""

    assessment = assess_volatility_risk(signal)
    metadata: dict[str, str | int | float | bool] = {
        "volatility_risk_authority": assessment.authority,
        "volatility_class": assessment.volatility_class.value,
        "volatility_source": assessment.source,
        "volatility_atr_percent": assessment.atr_percent or 0.0,
        "volatility_stop_atr_ratio": assessment.stop_atr_ratio or 0.0,
        "volatility_risk_score": assessment.risk_score,
        "volatility_risk_reasons": ",".join(assessment.reasons),
        "volatility_risk_elevated": assessment.elevated,
        "volatility_risk_would_block": False,
    }
    profile = signal.decision_volatility_profile
    if profile is not None:
        metadata.update(
            {key: value for key, value in profile.as_metadata().items() if value is not None}
        )
    return metadata
