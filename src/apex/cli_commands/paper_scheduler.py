"""Scheduler-ready spot and futures paper-cycle commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from apex.application import bootstrap, create_market_data_services
from apex.paper_trading import (
    PaperCycleAlreadyRunningError,
    PaperTradeConfig,
    PaperTradeStore,
    run_scheduled_paper_cycle,
)
from apex.presentation import (
    OutputMode,