"""Canonical market-usability classification from existing analysis metadata."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MarketUsabilityState(StrEnum):
    USABLE = "usable"
    USABLE_WITH_CAUTION = "usable_with_caution"
    UNUSABLE = "unusable"
    DATA_INCOMPLETE = "data_incomplete"


@dataclass(frozen=True, slots=True)
class MarketUsabilityAssessment:
    state: MarketUsabilityState
    score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or