"""Tests for read-only funded futures-plan reporting."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_plan_reporting import register_funded_plan_reporting_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_plan_reporting_commands(app)
    return app


def _payload(*, execution_author