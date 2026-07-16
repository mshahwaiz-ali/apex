"""Immutable contracts for deterministic futures trade lifecycle replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain.futures import FuturesDirection


class TradeLifecycleState(StrEnum):
    PENDING_ENTRY = "PENDING_ENTRY"
    ENTRY_FILLED = "ENTRY_FILLED"
    TP1_HIT = "TP1_HIT"
    BREAKEVEN_ACTIVE = "BREAKEVEN_ACTIVE"
    TP2_HIT = "TP2_H