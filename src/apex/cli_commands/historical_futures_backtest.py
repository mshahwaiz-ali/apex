"""CLI command for deterministic historical futures campaign backtesting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting import (
    BacktestConfig,
    HistoricalFuturesCampaignRequest,
    HistoricalFuturesExecutionManifest,
    execute_historical_futures_campaign,
    load_historical_signal_campaign_inputs,
    write_historical_futures_campaign,
)


def register_historical_f