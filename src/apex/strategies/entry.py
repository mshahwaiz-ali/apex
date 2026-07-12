"""Volatility-aware near-CMP entry-location selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.strategies.contracts import EntryMode, EntryZone, TradeDirection


@dataclass(frozen=True, slots=True)
class EntryReference:
    """A strategy-provided nearby location considered by the shared engine."""

    price: float
    mode: EntryMode
    rationale: tuple[str, ...]
   