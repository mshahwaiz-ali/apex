"""Immutable contracts for deterministic Phase 6 risk analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.strategies.contracts import StrategyType, TradeDirection


class RiskDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskRejectionCode(StrEnum):
    NO_SELECTED_CANDIDATE = "no_selected_candidate"
    ENTRY_TOO_EXTENDED = "entry_too_extended"
    STOP_TOO_TIGHT = "stop_too_tight"
    STOP_TOO_WIDE = "stop_too_wide"
    INSUFFICIENT_TARGET_SPACE = "insufficient_target_space"
    LEVERAGE_UNSAFE = "leverage_unsafe"
    MAX_CONCURRENT_TRADES = "max_concurrent