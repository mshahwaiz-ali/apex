from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_provider import register_funded_provider_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_provider_commands(app)
    return app


def _write_registry(path: Path) -> None:
    path.write_text(
        "schema_version: 1\n"
        "maximum_verification_age_days: 30\n"
        "presets:\n"
        "  - provider_id: EXAMPLE\n"
        "    provider_name: Example Funded\n"
        "    challenge_phase: PHASE_1\n"
        "    verified_on: '2026-07-01'\n"
        "    source_reference: https://example.invalid/rules\n"
        "    drawdown_model: STATIC\n"
        "    external_daily_drawdown_limit_pct: 5.0\n"
        "    external_total_drawdown_limit_pct: 10.0\n"
        "    maximum_trades_per_day