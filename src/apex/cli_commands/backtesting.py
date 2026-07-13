"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    ChronologicalBacktestRequest,
    bootstrap,
    create_market_data_services,