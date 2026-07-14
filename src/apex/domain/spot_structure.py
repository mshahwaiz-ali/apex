"""Deterministic higher-timeframe structure and regime engine for spot."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from apex.domain.spot import SpotMarketRegime


class SpotTrendState(StrEnum):
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    RANGE = "RANGE"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SpotExtensionState(StrEnum):
    NORMAL