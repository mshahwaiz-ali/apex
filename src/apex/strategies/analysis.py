"""Phase 4 strategy-candidate orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from apex.domain.futures import EntryState
from apex.strategies.context import StrategyContext, TimeframeRole
from apex.strategies