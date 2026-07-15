"""Deterministic Phase 4 rejection and near-miss diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from apex.domain.futures import EntryState
from apex.strategies.context import StrategyContext, TimeframeRole
from apex.strategies.contracts import StrategyType, TradeCandidate, TradeDirection
from apex.structure.contracts import BreakDirection, ConfirmationStatus