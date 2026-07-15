"""Scheduler-safe orchestration for paper intake followed by lifecycle advancement."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apex.paper_trading.intake import IntakeMarketType, IntakeSummary, intake_summary_payload
from apex.paper_trading.scheduler import PaperScheduled