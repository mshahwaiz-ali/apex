from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_pipeline as pipeline_cli
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.paper_trading.scheduler import ScheduledPaperCycleResult

runner = CliRunner()


def _app() -> typer.Typer:
   