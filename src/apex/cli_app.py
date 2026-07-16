"""Corrected Apex CLI entrypoint."""

from apex.cli import app, dataset_app, paper_app
from apex.cli_commands import install_cli_commands
from apex.cli_commands.aligned_dataset_campaigns import (
    register_aligned_dataset_campaign_commands,
)
from apex.cli_commands.dataset_campaigns import register_dataset_campaign_commands
from apex.cli_commands.historical_futures_backtest import (
    register_historical_futures_backtest_commands,
)
from apex.cli_commands.historical_signal_generation import (
    register_historical_signal_generation_commands,
)
from apex.cli_help import apply_curated_help
from apex.cli_navigation import install_professional_navigation

install_cli_commands(app, paper_app)
register_dataset_campaign_commands(dataset_app)
register_aligned_dataset_campaign_commands(dataset_app)
register_historical_signal_generation_commands(dataset_app)
register_historical_futures_backtest_commands(dataset_app)
apply_curated_help(app)
install_professional_navigation(app)

__all__ = ["app"]
