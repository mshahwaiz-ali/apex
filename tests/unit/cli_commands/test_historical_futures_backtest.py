"""Focused tests for the N4.8 historical futures backtest CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from apex.backtesting import HistoricalFuturesExecutionManifest
from apex.cli_app import app
from apex.cli_commands.historical_futures_backtest import _echo_completion

runner = CliRunner()