"""Canonical symbol wrappers for paper-trading CLI commands."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import typer

from apex.application import (
    AccountStateStore,
    analyze_symbol,
    bootstrap,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
