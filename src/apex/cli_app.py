"""Corrected Apex CLI entrypoint."""

from apex.cli import app, paper_app
from apex.cli_commands import install_cli_commands

install_cli_commands(app, paper_app)

__all__ = ["app"]
