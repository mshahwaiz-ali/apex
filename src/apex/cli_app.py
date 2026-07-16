"""Corrected Apex CLI entrypoint."""

from apex.cli import app, dataset_app, paper_app
from apex.cli_commands import install_cli_commands
from apex.cli_commands.aligned_dataset_campaigns import (
    register_aligned_dataset_campaign_commands,
)
from apex.cli_commands.dataset_campaigns import register_dataset_campaign_commands
from apex.cli_commands.historical_futures_backtest import (
    register_historical_futures_backtest_commands,
