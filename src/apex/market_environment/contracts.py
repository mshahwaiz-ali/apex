"""Strict contracts for deterministic market-environment classification and fusion."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class MarketRegime(StrEnum):
    """Canonical per-timeframe and fused market regimes."""

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    BREAKOUT_EXPANSION_UP = "BREAKOUT_EXPANSION_UP"
    BREAKOUT_EXPANSION_DOWN = "BREAKOUT_EXPANSION_DOWN"
    BREAKOUT_RETEST_UP = "BREAKOUT_RETEST_UP"
    BREAKOUT_RETEST_DOWN = "BREAKOUT_RETEST_DOWN"
    FAILED_BREAKOUT_UP = "FAILED_BREAKOUT_UP"
    FAILED_BREAKOUT_DOWN = "FAILED_BREAKOUT_DOWN"
    SQUEEZE = "SQUEEZE"
    EXHAUSTION_UP = "EXHAUSTION_UP"
    EXHAUSTION_DOWN = "EXHAUSTION_DOWN"
    REVERSAL_UP = "REVERSAL_UP"
    REVERSAL_DOWN = "REVERSAL_DOWN"
    NOISY = "NOISY"
    UNTRADEABLE = "UNTRADEABLE"
    UNKNOWN = "UNKNOWN"


class HigherTimeframeBias(StrEnum):
    STRONGLY_BULLISH = "STRONGLY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONGLY_BEARISH = "STRONGLY_BEARISH"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class VolatilityState(StrEnum):
    COMPRESSED = "COMPRESSED"
    NORMAL = "NORMAL"
    EXPANDING = "EXPANDING"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


class ExtensionState(StrEnum):
    UNDEREXTENDED = "UNDEREXTENDED"
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    OVEREXTENDED = "OVEREXTENDED"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


class ConflictState(StrEnum):
    NONE = "NONE"
    STRUCTURAL_CONFLICT = "STRUCTURAL_CONFLICT"
    TIMING_CONFLICT = "TIMING_CONFLICT"
    EXTENSION_WARNING = "EXTENSION_WARNING"
    VOLATILITY_WARNING = "VOLATILITY_WARNING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class InputCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class TimeframeMarketSnapshot:
    """Available canonical inputs for one timeframe without fabricated values."""

    timeframe: str
    candle_timestamp: datetime | None
    current_price: float
    last_closed_price: float | None
    recent_swing_high: float | None
    recent_swing_low: float | None
    trend_direction: str
    ema_fast: float | None
    ema_slow: float | None
    ema_slope: float | None
    vwap: float | None
    atr: float
    candle_body_ratio: float | None
    upper_wick_ratio: float | None
    lower_wick_ratio: float | None
    volume: float | None
    relative_volume: float | None
    rsi: float | None
    macd_histogram: float | None
    recent_high_break: bool | None
    recent_low_break: bool | None
    consolidation: bool | None
    compression: bool | None
    range_position: float | None
    volatility_expansion: float | None
    data_confidence: float
    missing_data: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty")
        if not math.isfinite(self.current_price) or self.current_price <= 0:
            raise ValueError("current price must be positive and finite")
        if not math.isfinite(self.atr) or self.atr <= 0:
            raise ValueError("ATR must be positive and finite")
        if self.candle_timestamp is not None and (
            self.candle_timestamp.tzinfo is None
            or self.candle_timestamp.utcoffset() is None
        ):
            raise ValueError("candle timestamp must be timezone-aware")
        for name in (
            "last_closed_price",
            "recent_swing_high",
            "recent_swing_low",
            "ema_fast",
            "ema_slow",
            "vwap",
        ):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name.replace('_', ' ')} must be positive and finite")
        for name in (
            "ema_slope",
            "candle_body_ratio",
            "upper_wick_ratio",
            "lower_wick_ratio",
            "volume",
            "relative_volume",
            "rsi",
            "macd_histogram",
            "range_position",
            "volatility_expansion",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        for name in (
            "candle_body_ratio",
            "upper_wick_ratio",
            "lower_wick_ratio",
            "range_position",
            "data_confidence",
        ):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and one")
        if self.volatility_expansion is not None and self.volatility_expansion < 0:
            raise ValueError("volatility expansion cannot be negative")
        if self.relative_volume is not None and self.relative_volume < 0:
            raise ValueError("relative volume cannot be negative")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.rsi is not None and not 0 <= self.rsi <= 100:
            raise ValueError("RSI must be between zero and 100")
        if len(set(self.missing_data)) != len(self.missing_data):
            raise ValueError("missing-data markers must be unique")

    @property
    def ema_ordering(self) -> str | None:
        if self.ema_fast is None or self.ema_slow is None:
            return None
        if self.ema_fast > self.ema_slow:
            return "bullish"
        if self.ema_fast < self.ema_slow:
            return "bearish"
        return "flat"

    @property
    def price_to_vwap_atr(self) -> float | None:
        if self.vwap is None:
            return None
        return (self.current_price - self.vwap) / self.atr

    @property
    def price_to_ema_mean_atr(self) -> float | None:
        if self.ema_fast is None or self.ema_slow is None:
            return None
        mean = (self.ema_fast + self.ema_slow) / 2.0
        return (self.current_price - mean) / self.atr


@dataclass(frozen=True, slots=True)
class TimeframeRegimeResult:
    snapshot: TimeframeMarketSnapshot
    regime: MarketRegime
    volatility_state: VolatilityState
    extension_state: ExtensionState
    bullish_score: float
    bearish_score: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("bullish_score", "bearish_score"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and 100")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason codes must be unique")


@dataclass(frozen=True, slots=True)
class MarketEnvironment:
    """Deterministic multi-timeframe environment used by routing and reporting."""

    primary_regime: MarketRegime
    higher_timeframe_bias: HigherTimeframeBias
    execution_timeframe: str
    entry_timeframe: str
    alignment_score: float
    conflict_score: float
    conflict_state: ConflictState
    volatility_state: VolatilityState
    extension_state: ExtensionState
    tradeable: bool
    long_suitability_score: float
    short_suitability_score: float
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    missing_timeframes: tuple[str, ...]
    input_completeness: InputCompleteness
    timeframe_regimes: Mapping[str, TimeframeRegimeResult]

    def __post_init__(self) -> None:
        if not self.execution_timeframe.strip() or not self.entry_timeframe.strip():
            raise ValueError("execution and entry timeframes cannot be empty")
        for name in (
            "alignment_score",
            "conflict_score",
            "long_suitability_score",
            "short_suitability_score",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and 100")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason codes must be unique")
        if len(set(self.missing_timeframes)) != len(self.missing_timeframes):
            raise ValueError("missing timeframes must be unique")
        object.__setattr__(
            self,
            "timeframe_regimes",
            MappingProxyType(dict(self.timeframe_regimes)),
        )
