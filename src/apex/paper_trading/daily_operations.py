"""Idempotent scheduled daily reporting for P1 paper validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from apex.paper_trading.forward_validation import (
    ForwardPaperDailyReport,
    build_forward_paper_daily_report,
    load_and_verify_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.paper_trading.store import Paper