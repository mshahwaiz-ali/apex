"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

from collections.abc import Mapping
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
    normalize_market_symbol,
    parse_campaign_variants,
    run_backtest_campaign,
    run_chronological_pipeline_backtest,
    run_multi_symbol_backtest_campaign,
    split_campaign_candles_by_symbol,
)
from apex.application.backtest_comparison import compare_backtest_reports
from apex.application.backtest_report