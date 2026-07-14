"""Canonical symbol wrappers for paper-trading CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apex.application import (
    AccountStateStore,
    analyze_symbol,
    bootstrap,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    serialize_symbol_analysis,
)
from apex.application.account_context import resolve_account_context
from apex.application.exposure