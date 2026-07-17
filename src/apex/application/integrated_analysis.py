"""Market-environment-aware wrappers for live discovery analysis and scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.application import discovery_analysis as _analysis
from apex.application.market_state import (
    MarketStateSnapshot,
    classify_market_state,
    market_state_payload,