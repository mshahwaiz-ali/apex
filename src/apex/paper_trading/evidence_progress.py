"""Forward-paper evidence progress by canonical setup segment."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any

from apex.paper_trading.contracts import PaperTrade, PaperTradeState

_CLOSED_OUTCOME_STATES = {PaperTradeState.STOPPED, PaperTradeState.TARGET_HIT}


@dataclass(frozen=True, slots=True)
class EvidenceProgressSegment:
    dimensions: dict[str, str]
    closed_trade_count: int
    required