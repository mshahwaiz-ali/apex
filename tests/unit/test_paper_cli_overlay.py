"""Focused CLI coverage for the corrected paper-command overlay."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_trading as paper_cli


runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    paper_cli.register_paper_trading_commands(app)