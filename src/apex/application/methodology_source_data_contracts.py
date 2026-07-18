"""Canonical physical source metadata for methodology evidence and confirmation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SourceCandleMetadata:
    """Identity, timing, and physical closure state for one source candle."""

    source_id: str
    symbol: str
    timeframe: str
    provider: str
    opened_at: datetime
    closes_at: datetime
    observed_at: datetime
    is_closed: bool
    expected_interval_seconds: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("source id", self.source_id),
            ("symbol", self.symbol),
            ("timeframe", self.timeframe),
            ("provider", self.provider),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        for name, value in (
            ("opened at", self.opened_at),
            ("closes at", self.closes_at),
            ("observed at", self.observed_at),
        ):
            _aware(name, value)
        if self.closes_at <= self.opened_at:
            raise ValueError("source candle close must be after open")
        if self.is_closed and self.observed_at < self.closes_at:
            raise ValueError("closed source candle cannot be observed before its close")
        if self.expected_interval_seconds is not None:
            if not math.isfinite(self.expected_interval_seconds):
                raise ValueError("expected interval seconds must be finite")
            if self.expected_interval_seconds <= 0.0:
                raise ValueError("expected interval seconds must be positive")

    @property
    def age_seconds(self) -> float:
        """Elapsed time from physical candle close to observation."""

        return max(0.0, (self.observed_at - self.closes_at).total_seconds())

    @property
    def age_intervals(self) -> float | None:
        """Age normalized by explicit expected interval duration when available."""

        if self.expected_interval_seconds is None:
            return None
        return self.age_seconds / self.expected_interval_seconds


@dataclass(frozen=True, slots=True)
class EvidenceSourceReference:
    """Link one canonical evidence observation to physical source metadata."""

    evidence_index: int
    source_id: str

    def __post_init__(self) -> None:
        if self.evidence_index < 0:
            raise ValueError("evidence index cannot be negative")
        if not self.source_id.strip():
            raise ValueError("source id cannot be empty")


__all__ = ["EvidenceSourceReference", "SourceCandleMetadata"]
