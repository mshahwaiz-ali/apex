"""Mode-aware market scanner CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    bootstrap,
    build_analysis_record,
    create_market_data_services,
    format_scan_text,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
    write_analysis_record,
    write_analysis_record_sqlite