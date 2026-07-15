"""Focused tests for the schema-v2 historical signal campaign CLI."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.cli_app