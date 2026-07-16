"""Combined automatic intake and lifecycle paper pipeline commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

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
from apex.application.paper_intake import append_intake_log, intake_futures_scan, intake_spot_scan
from apex.application.paper_lifecycle_analytics import (
    build_p