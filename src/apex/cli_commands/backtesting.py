"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

from collections.abc import Mapping
from math import ceil
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    BacktestCampaignRequest,
    ChronologicalBacktestRequest,
    MultiSymbolBacktestCampaignRequest,
    bootstrap,
    campaign_result_to_payload,
    create_market_data_services,
    load_default_risk_config,