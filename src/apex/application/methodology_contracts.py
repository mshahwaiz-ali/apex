"""Canonical contracts for the trade-plan methodology pipeline.

These contracts provide one vocabulary across discovery, strategy routing,
execution geometry, scoring, rejection, presentation, and backtesting. They are
introduced without changing live trade behavior; existing layers can migrate to
them incrementally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Str