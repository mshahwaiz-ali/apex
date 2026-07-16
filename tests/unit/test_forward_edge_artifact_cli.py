from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.forward_edge_artifact import register_forward_edge_artifact_commands
from apex.cli_commands.forward_edge_artifact_verify import (
    register_forward_edge_artifact_verify_commands,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_forward_edge_artifact_commands(app)
    register_forward_edge_artifact_verify_commands(app)
    return app


def _write_report(path: Path) -> None:
    path