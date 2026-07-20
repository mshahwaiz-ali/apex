"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    build_analysis_record,
    configuration_metadata,
    create_market_data_services,
    reconcile_pending_opportunities_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
