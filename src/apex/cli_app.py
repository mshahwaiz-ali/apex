"""Focused Apex CLI entrypoint."""

from apex.cli import app
from apex.cli_commands import install_cli_commands
from apex.cli_help import apply_curated_help
from apex.cli_navigation import install_professional_navigation

install_cli_commands(app)
apply_curated_help(app)
install_professional_navigation(app)

__all__ = ["app"]
