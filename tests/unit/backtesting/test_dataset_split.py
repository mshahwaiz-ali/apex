"""Deterministic chronological futures-dataset split tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting import (
    FuturesCandleDataset,
    FuturesDatasetSplitRatios,
    FuturesDatasetSplitSet,
    allocate_split_counts,
    build_futures