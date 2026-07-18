"""Canonical evidence for target obstacles and execution costs."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.application.methodology_contracts import TargetRole


def _non_negative(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0:
        raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True,