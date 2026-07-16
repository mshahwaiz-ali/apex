"""Scheduler-friendly automatic futures and spot paper opportunity intake."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    bootstrap,
    build_futures_account_input,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
)
from apex.application.paper_intake import (
    intake_futures_scan,
    intake_spot_scan,
    run_locked_paper_intake,
)
from apex.application.spot_live import load_spot_live_account
from apex.application.spot_live_scanner import scan_live_spot
from apex.application.sp