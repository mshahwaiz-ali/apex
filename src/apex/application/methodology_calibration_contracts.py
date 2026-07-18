"""Canonical provenance for historical calibration and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CalibrationProvenance:
    """Evidence required before a historical probability can be authoritative