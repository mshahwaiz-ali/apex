"""Typed multi-timeframe context consumed by Phase 4 strategies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.liquidity.analysis import LiquidityAnalysisResult
from apex.structure.contracts import StructureAnalysisResult, TrendDirection


class TimeframeRole(StrEnum):
    LONG_TERM_MACRO = "long_term_macro"
    SWING = "swing"
    MACRO = "macro"
    INTERMEDIATE = "intermediate"
    INTRADAY = "intraday"
    SETUP = "setup"
    ENTRY = "entry"
    REFINEMENT = "refinement"
    TIMING = "timing"


_ROLE_ORDER = {
    TimeframeRole.LONG_TERM_MACRO: 0,
    TimeframeRole.SWING: 1,
    TimeframeRole.MACRO: 2,
    TimeframeRole.INTERMEDIATE: 3,
    TimeframeRole.INTRADAY: 4,
    TimeframeRole.SETUP: 5,
    TimeframeRole.ENTRY: 6,
    TimeframeRole.REFINEMENT: 7,
    TimeframeRole.TIMING: 8,
}


def timeframe_role_sort_key(role: TimeframeRole) -> int:
    """Return stable highest-to-lowest ordering for configured timeframe roles."""

    return _ROLE_ORDER[role]


def _finite(name: str, value: float | None) -> None:
    if value is not None and not math.isfinite(value):
        raise ValueError(f"{name} must be finite when provided")


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    atr: float
    ema_fast: float | None = None
    ema_slow: float | None = None
    vwap: float | None = None
    rsi: float | None = None
    rsi_slope: float | None = None
    stochastic: float | None = None
    stochastic_rsi: float | None = None
    macd_histogram: float | None = None
    rate_of_change: float | None = None
    relative_volume: float | None = None
    trend_strength: float | None = None
    range_position: float | None = None
    volatility_expansion: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.atr) or self.atr <= 0:
            raise ValueError("ATR must be positive and finite")
        for name in (
            "ema_fast",
            "ema_slow",
            "vwap",
            "rsi",
            "rsi_slope",
            "stochastic",
            "stochastic_rsi",
            "macd_histogram",
            "rate_of_change",
            "relative_volume",
            "trend_strength",
            "range_position",
            "volatility_expansion",
        ):
            _finite(name.replace("_", " "), getattr(self, name))
        for name in ("ema_fast", "ema_slow", "vwap"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name.replace('_', ' ')} must be positive")
        for name in ("rsi", "stochastic", "stochastic_rsi"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and 100")
        for name in ("trend_strength", "range_position", "volatility_expansion"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and one")
        if self.relative_volume is not None and self.relative_volume < 0:
            raise ValueError("relative volume cannot be negative")


@dataclass(frozen=True, slots=True)
class TimeframeContext:
    timeframe: str
    role: TimeframeRole
    current_price: float
    features: FeatureSnapshot
    structure: StructureAnalysisResult
    liquidity: LiquidityAnalysisResult
    active_candle: bool = False

    def __post_init__(self) -> None:
        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty")
        if not math.isfinite(self.current_price) or self.current_price <= 0:
            raise ValueError("current price must be positive and finite")


@dataclass(frozen=True, slots=True)
class StrategyContext:
    symbol: str
    frames: tuple[TimeframeContext, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("strategy-context symbol cannot be empty")
        if not self.frames:
            raise ValueError("strategy context requires at least one timeframe")
        expected = tuple(sorted(self.frames, key=lambda frame: _ROLE_ORDER[frame.role]))
        if expected != self.frames:
            raise ValueError("timeframes must use stable highest-to-lowest role ordering")
        names = tuple(frame.timeframe for frame in self.frames)
        roles = tuple(frame.role for frame in self.frames)
        if len(set(names)) != len(names):
            raise ValueError("timeframe names must be unique")
        if len(set(roles)) != len(roles):
            raise ValueError("timeframe roles must be unique")
        thesis_roles = {
            TimeframeRole.LONG_TERM_MACRO,
            TimeframeRole.SWING,
            TimeframeRole.MACRO,
            TimeframeRole.INTERMEDIATE,
            TimeframeRole.INTRADAY,
            TimeframeRole.SETUP,
            TimeframeRole.ENTRY,
        }
        if not any(frame.role in thesis_roles for frame in self.frames):
            raise ValueError("timing-only timeframes cannot establish a trade thesis")

    @property
    def decision_frame(self) -> TimeframeContext:
        for role in (TimeframeRole.ENTRY, TimeframeRole.SETUP, TimeframeRole.INTRADAY):
            for frame in self.frames:
                if frame.role is role:
                    return frame
        return self.frames[0]

    @property
    def current_price(self) -> float:
        return self.decision_frame.current_price

    @property
    def atr(self) -> float:
        return self.decision_frame.features.atr

    @property
    def provisional(self) -> bool:
        return any(frame.active_candle for frame in self.frames)

    def higher_timeframe_contradiction(self, *, bullish: bool) -> bool:
        opposed = (
            {
                TrendDirection.STRONG_BEARISH,
                TrendDirection.BEARISH,
            }
            if bullish
            else {
                TrendDirection.STRONG_BULLISH,
                TrendDirection.BULLISH,
            }
        )
        return any(
            frame.structure.trend.direction in opposed
            for frame in self.frames
            if frame.role
            in {
                TimeframeRole.LONG_TERM_MACRO,
                TimeframeRole.SWING,
                TimeframeRole.MACRO,
                TimeframeRole.INTERMEDIATE,
            }
        )
