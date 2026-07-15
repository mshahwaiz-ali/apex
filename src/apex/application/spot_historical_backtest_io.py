"""Persistence verification for deterministic historical spot backtests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from apex.application.spot_historical_backtest import (
    SpotHistoricalBacktestManifest,
    SpotHistoricalBacktestResult,
)


def load_and_verify_spot_historical_backtest(
    *,
    result_path: Path,
