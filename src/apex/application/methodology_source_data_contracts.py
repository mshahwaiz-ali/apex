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
    """Identity and physical closure state for