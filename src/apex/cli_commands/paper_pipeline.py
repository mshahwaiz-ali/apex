"""Combined automatic intake and lifecycle paper pipeline commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
from apex.application.paper_intake import intake_futures_scan, intake_spot_scan
from apex.application.paper_pipeline import paper_pipeline_payload, run_locked_paper_pipeline
from apex.application.spot_live import load_spot_live_account
from apex.application.spot_live_scanner import scan_live_spot
from apex.application.spot_orchestration_io import (
    DEFAULT_SPOT_CONFIG_PATH,
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strateg