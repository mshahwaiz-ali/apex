"""Strict contracts for deterministic market-environment classification and fusion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from collections.abc import Mapping


class MarketRegime(StrEnum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    BREAKOUT