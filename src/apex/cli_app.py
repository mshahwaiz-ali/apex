"""Corrected Apex CLI entrypoint."""

from apex.cli import app, dataset_app, paper_app
from apex.cli_commands import install_cli_commands
from apex.cli_commands.dataset_campaigns import register_dataset_campaign_commands

install_cli_commands(app, paper_app)
register_dataset_campaign_commands(dataset_app)

__all__ = ["app"]
