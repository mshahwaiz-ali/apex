"""Typed production analytics for paper intake, execution, and lifecycle outcomes."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import fmean
from typing import Any

from apex.paper_trading.contracts import PaperTrade, PaperTradeState, TERMINAL_STATES
from apex.paper_trading.intake import IntakeSummary
from apex.paper_trading.runtime import PaperRuntimeResult

__all__ = [
    "Holding