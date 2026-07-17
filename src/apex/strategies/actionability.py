"""Deterministic discovery-only candidate actionability classification."""

from __future__ import annotations

from collections.abc import Sequence

from apex.strategies.contracts import EntryMode, TradeCandidate, TradeDirection
from apex.strategies.entry_status import ENTRY_STATUS_PRECEDENCE, EntryStatus

_AGGRESSIVE_MAX_ATR_DISTANCE = 0.35
_AGGRESSIVE_MIN_LOCATION_QUALITY = 0.60
_PULLBACK_MAX_ATR_DISTANCE = 1.50
_PULLBACK_MODES = {