"""Immutable contracts for optional Phase 11 market intelligence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FundingRateSnapshot:
    symbol: str
    funding_rate: float
    captured_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.source.strip():
            raise ValueError("funding snapshot symbol and source cannot be empty")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("funding snapshot time must be timezone-aware")
        if not math.isfinite(self.funding_rate):
            raise ValueError("funding rate must be finite")


@dataclass(frozen=True, slots=True)
class OpenInterestSnapshot:
    symbol: str
    open_interest: float
    captured_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.source.strip():
            raise ValueError("open-interest snapshot symbol and source cannot be empty")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("open-interest snapshot time must be timezone-aware")
        if not math.isfinite(self.open_interest) or self.open_interest < 0.0:
            raise ValueError("open interest must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SymbolCorrelation:
    base_symbol: str
    compared_symbol: str
    correlation: float
    sample_size: int

    def __post_init__(self) -> None:
        if not self.base_symbol.strip() or not self.compared_symbol.strip():
            raise ValueError("correlation symbols cannot be empty")
        if not math.isfinite(self.correlation) or not -1.0 <= self.correlation <= 1.0:
            raise ValueError("correlation must be finite and between -1 and 1")
        if self.sample_size < 2:
            raise ValueError("correlation sample size must be at least two")


@dataclass(frozen=True, slots=True)
class MarketWideRiskSummary:
    risk_score: float
    warnings: tuple[str, ...]
    funding: tuple[FundingRateSnapshot, ...] = ()
    open_interest: tuple[OpenInterestSnapshot, ...] = ()
    correlations: tuple[SymbolCorrelation, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.risk_score) or not 0.0 <= self.risk_score <= 1.0:
            raise ValueError("risk score must be in the unit interval")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("risk warnings must be unique")
