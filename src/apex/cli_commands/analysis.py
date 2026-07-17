"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    build_analysis_record,
    create_market_data_services,
    serialize_symbol_analysis,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import normalize_cli_output_mode
from apex.presentation.futures import render_futures_analysis

_REMOVED_PUBLIC_FIELDS = {
    "execution