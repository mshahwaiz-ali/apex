"""Corrected Apex CLI entrypoint."""

from apex.cli import app
from apex.cli_commands import install_cli_commands

install_cli_commands(app)

__all__ = ["app"]
