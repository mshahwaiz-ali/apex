"""Strategy-routing and near-current-entry orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.application import analysis as _analysis
from apex.application import integrated_analysis as _integrated
from apex.application.market_strategy_router import (
