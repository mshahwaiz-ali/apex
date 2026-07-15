"""Scheduler-safe wrapper for provider-backed paper cycles."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from apex.paper_trading.runtime import CandleProvider, PaperRuntimeResult, run_provider_backed_paper_cycle
from apex.paper_trading.store import PaperTradeStore


@dataclass(frozen=True, slots=True)
class