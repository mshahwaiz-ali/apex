"""Corrected Apex CLI surface layered over the existing command set."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import typer

from apex.application import (
    ChronologicalBacktestRequest,
    analyze_selected_symbol,
    bootstrap,
    create_market_data_services,
    format_symbol_text,
    load_default_risk_config,
    normalize_market_symbol,
    run_chronological_pipeline_backtest,
    serialize_symbol_analysis,
)
from apex.cli import app
from apex.cli