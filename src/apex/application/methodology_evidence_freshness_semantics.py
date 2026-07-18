"""Interpret methodology evidence freshness without inventing candle timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessSemantics:
    """Public interpretation of canonical evidence freshness metadata."""

    evidence_count: int
    freshness